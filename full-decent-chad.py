from nacl import signing, encoding, hash
import json, time, base64


# ----------------------------
# Helpers
# ----------------------------

def canonical_json(obj) -> bytes:
    """
    Deterministic JSON encoding:
    - sorted keys
    - no whitespace
    - UTF-8 bytes
    """
    return json.dumps(
        obj,
        separators=(",", ":"),
        sort_keys=True,
        ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(b: bytes) -> bytes:
    return hash.sha256(b)


def b64(b: bytes) -> str:
    return base64.b64encode(b).decode("ascii")


def b64_to_bytes(s: str) -> bytes:
    return base64.b64decode(s.encode("ascii"))


# ----------------------------
# Feed database
# ----------------------------

class FeedDB:
    """
    Stores messages and supports:
    - append (author feed)
    - lookup by (author, seq)
    - head state per author
    """

    def __init__(self, name="db"):
        self.name = name
        self.by_id = {}              # msg_id -> signed message dict
        self.by_author_seq = {}      # (author_pub_b64, seq) -> msg_id
        self.head = {}               # author_pub_b64 -> (latest_seq, latest_msg_id)

    def latest(self, author_pub_b64: str):
        return self.head.get(author_pub_b64, (0, None))

    def get_id_at_seq(self, author_pub_b64: str, seq: int):
        return self.by_author_seq.get((author_pub_b64, seq))

    def get_msg_at_seq(self, author_pub_b64: str, seq: int):
        mid = self.get_id_at_seq(author_pub_b64, seq)
        if mid is None:
            return None
        return self.by_id[mid]

    def store(self, author_pub_b64: str, seq: int, msg_id: str, signed_msg: dict):
        self.by_id[msg_id] = signed_msg
        self.by_author_seq[(author_pub_b64, seq)] = msg_id
        self.head[author_pub_b64] = (seq, msg_id)

    def has_author(self, author_pub_b64: str) -> bool:
        return author_pub_b64 in self.head


# ----------------------------
# SSB-like append + verify
# ----------------------------

def append_message(db: FeedDB, author_signing_key: signing.SigningKey, content_obj: dict):
    """
    Append a new message to the author's feed:
    - unsigned message = author, seq, previous, timestamp, content
    - signature = Ed25519(private_key, bytes(unsigned))
    - msg_id = SHA256(bytes(signed_message))
    """

    author_pub_b64 = author_signing_key.verify_key.encode(
        encoder=encoding.Base64Encoder
    ).decode("ascii")

    last_seq, last_id = db.latest(author_pub_b64)

    unsigned = {
        "author": author_pub_b64,
        "sequence": last_seq + 1,
        "previous": last_id,  # None for first message
        "timestamp": int(time.time() * 1000),
        "content": content_obj
    }

    unsigned_bytes = canonical_json(unsigned)
    signature_bytes = author_signing_key.sign(unsigned_bytes).signature

    signed_msg = dict(unsigned)
    signed_msg["signature"] = b64(signature_bytes)

    msg_id = b64(sha256_bytes(canonical_json(signed_msg)))

    db.store(author_pub_b64, signed_msg["sequence"], msg_id, signed_msg)
    return msg_id, signed_msg


def verify_message(db: FeedDB, msg_id: str, signed_msg: dict):
    """
    Verify:
    1) signature is valid for unsigned message bytes
    2) chain continuity: previous pointer and seq
    3) msg_id matches hash(signed_msg_bytes)
    """

    author_pub_b64 = signed_msg["author"]
    signature_bytes = b64_to_bytes(signed_msg["signature"])

    # reconstruct unsigned
    unsigned = dict(signed_msg)
    unsigned.pop("signature", None)
    unsigned_bytes = canonical_json(unsigned)

    # signature check
    vk = signing.VerifyKey(author_pub_b64, encoder=encoding.Base64Encoder)
    try:
        vk.verify(unsigned_bytes, signature_bytes)
    except Exception:
        return False, "bad_signature"

    seq = signed_msg["sequence"]
    prev = signed_msg["previous"]

    # continuity check
    if seq == 1:
        if prev is not None:
            return False, "seq1_previous_must_be_null"
    else:
        expected_prev = db.get_id_at_seq(author_pub_b64, seq - 1)
        if expected_prev is None:
            return False, "missing_history"
        if expected_prev != prev:
            return False, "fork_or_tamper"

    # msg_id check
    recomputed = b64(sha256_bytes(canonical_json(signed_msg)))
    if recomputed != msg_id:
        return False, "msg_id_mismatch"

    return True, "ok"


# ----------------------------
# Replication logic
# ----------------------------

def get_have_vector(db: FeedDB):
    """
    Returns what this node has:
      { author_pub_b64: latest_seq }
    """
    return {author: seq for author, (seq, _) in db.head.items()}


def get_missing_ranges(local_db: FeedDB, remote_have: dict):
    """
    Decide what we want from a remote peer.

    If remote has seq M for an author and we have seq N (<M),
    then we want messages (N+1..M).

    Returns:
      { author_pub_b64: (start_seq, end_seq) }
    """
    wants = {}
    for author, remote_seq in remote_have.items():
        local_seq, _ = local_db.latest(author)
        if remote_seq > local_seq:
            wants[author] = (local_seq + 1, remote_seq)
    return wants


def send_messages_in_range(db: FeedDB, author: str, start_seq: int, end_seq: int):
    """
    Fetch messages to send for replication.
    """
    out = []
    for seq in range(start_seq, end_seq + 1):
        msg = db.get_msg_at_seq(author, seq)
        if msg is None:
            break
        msg_id = db.get_id_at_seq(author, seq)
        out.append((msg_id, msg))
    return out


def replicate(from_db: FeedDB, to_db: FeedDB):
    """
    Simulate: to_db connects to from_db and syncs missing messages.
    """

    # 1) to_db asks: "what feeds and sequences do you have?"
    from_have = get_have_vector(from_db)

    # 2) to_db decides what it wants
    wants = get_missing_ranges(to_db, from_have)

    # 3) from_db sends the missing messages
    received = 0
    rejected = 0

    for author, (start_seq, end_seq) in wants.items():
        msgs = send_messages_in_range(from_db, author, start_seq, end_seq)

        for msg_id, signed_msg in msgs:
            ok, reason = verify_message(to_db, msg_id, signed_msg)

            if ok:
                # store it
                to_db.store(author, signed_msg["sequence"], msg_id, signed_msg)
                received += 1
            else:
                rejected += 1
                # In a real system you'd request missing history, log fork, etc.
                print(f"[{to_db.name}] REJECT {author} seq={signed_msg['sequence']} reason={reason}")

    return received, rejected


# ----------------------------
# Demo scenario
# ----------------------------

if __name__ == "__main__":
    # Node A = Alice's device (author)
    nodeA = FeedDB(name="NodeA")
    alice = signing.SigningKey.generate()

    # NodeB = Bob (follower)
    nodeB = FeedDB(name="NodeB")

    # NodeC = Carol (a peer who might act as store-and-forward)
    nodeC = FeedDB(name="NodeC")

    # Alice writes 3 posts
    append_message(nodeA, alice, {"type": "post", "text": "Post #1"})
    append_message(nodeA, alice, {"type": "post", "text": "Post #2"})
    append_message(nodeA, alice, {"type": "post", "text": "Post #3"})

    print("\n--- Bob syncs directly from Alice ---")
    r, rej = replicate(nodeA, nodeB)
    print(f"Bob received {r}, rejected {rej}")

    # Alice writes 2 more posts (Bob is offline now)
    append_message(nodeA, alice, {"type": "post", "text": "Post #4"})
    append_message(nodeA, alice, {"type": "post", "text": "Post #5"})

    print("\n--- Carol syncs from Alice (while Bob is offline) ---")
    r, rej = replicate(nodeA, nodeC)
    print(f"Carol received {r}, rejected {rej}")

    print("\n--- Bob comes back online, syncs from Carol (Alice could be offline) ---")
    r, rej = replicate(nodeC, nodeB)
    print(f"Bob received {r}, rejected {rej}")

    # Show Bob's latest feed state for Alice
    alice_pub = alice.verify_key.encode(encoder=encoding.Base64Encoder).decode("ascii")
    print("\nBob latest for Alice:", nodeB.latest(alice_pub))
