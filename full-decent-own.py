import json

def append_message(message):
    json_message = {
        "type": "post",
        "post_id"
    }
    return message

# I'm calling a 'Block' any signed object added to the author feed (the 'chain')
# Because there will be different types of admin blocks as well as comments
#   (eventually, hopefully) I'm differentiating a Post as just one type of Block
class Block_Post:
    def __init__(self, message):
        self.backlink = ""
        self.author_public_key =
        self.type = "post"
        self.post_id =

class Author_Feed:
    def __init__(self):

