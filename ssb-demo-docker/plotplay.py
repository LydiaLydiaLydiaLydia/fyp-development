from propagation_demo import scenario_result
import time

pr = {}
posted = time.time() - 300
pr.update({"ssb-sim-node-14" : {'elapsed' : 879.644, 'elapsed_human': "0 minutes 0 seconds 879.644 miliseconds", 'lan' : "ssb-sim-lan-2", 'received' : True}})
pr.update({"ssb-sim-node-11" : {'elapsed' : 1285.553, 'elapsed_human': "0 minutes 1 seconds 285.553 miliseconds", 'lan' : "ssb-sim-lan-2", 'received' : True}})
pr.update({"ssb-sim-node-2" : {'elapsed' : 2118.367, 'elapsed_human': "0 minutes 2 seconds 118.367 miliseconds", 'lan' : "ssb-sim-lan-2", 'received' : True}})
pr.update({"ssb-sim-node-3" : {'elapsed' : 1694.217, 'elapsed_human': "0 minutes 1 seconds 694.217 miliseconds", 'lan' : "ssb-sim-lan-3", 'received' : True}})
pr.update({"ssb-sim-node-12" : {'elapsed' : None, 'elapsed_human': "0 minutes 0 seconds 0 miliseconds", 'lan' : "ssb-sim-lan-3", 'received' : False}})

sr = scenario_result('random_dropout', "DFXBq/IQT9VOOOd0U/tJPnMLE2mYQbWwINRO4U+JoM=.sha256" , time.time() - 300,  {'ssb-sim-node-5', 'ssb-sim-node-4', 'ssb-sim-node-8', 'ssb-sim-node-9', 'ssb-sim-node-10'}, pr, None)

#==================================================
#2026-04-07 16:11:47 | INFO     |   SCENARIO: RANDOM_DROPOUT
#2026-04-07 16:11:47 | INFO     | ==================================================
#2026-04-07 16:11:47 | INFO     |   Message ID : %rDFXBq/IQT9VOOOd0U/tJPnMLE2mYQbWwINRO4U+JoM=.sha256
#2026-04-07 16:11:47 | INFO     |   Posted at  : 16:11:28.504
#2026-04-07 16:11:47 | INFO     |   Nodes down : {'ssb-sim-node-5', 'ssb-sim-node-4', 'ssb-sim-node-8', 'ssb-sim-node-9', 'ssb-sim-node-10'}
#2026-04-07 16:11:47 | INFO     |   Completion : 100%
#2026-04-07 16:11:47 | INFO     |   Median     : 0 minutes 1 seconds 694.217 miliseconds
#2026-04-07 16:11:47 | INFO     | 

#2026-04-07 16:11:47 | INFO     |   NODE                      LAN                RECEIVED   ELAPSED
#2026-04-07 16:11:47 | INFO     |   ------------------------ ----------------- --------- ---------------
#2026-04-07 16:11:47 | INFO     |   ssb-sim-node-14           ssb-sim-lan-2      yes        0 minutes 0 seconds 879.644 miliseconds
#2026-04-07 16:11:47 | INFO     |   ssb-sim-node-11           ssb-sim-lan-2      yes        0 minutes 1 seconds 285.553 miliseconds
#2026-04-07 16:11:47 | INFO     |   ssb-sim-node-2            ssb-sim-lan-2      yes        0 minutes 2 seconds 118.367 miliseconds
#2026-04-07 16:11:47 | INFO     |   ssb-sim-node-3            ssb-sim-lan-3      yes        0 minutes 1 seconds 694.217 miliseconds
#2026-04-07 16:11:47 | INFO     |   ssb-sim-node-12           ssb-sim-lan-3      yes        0 minutes 2 seconds 484.214 miliseconds