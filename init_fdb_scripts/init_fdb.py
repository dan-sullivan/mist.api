import fdb
fdb.api_version(610)

import fdb.tuple
import datetime
import random 
import json

MACHINE_ID = '6e2faf7bba844833841fe1e015afc841'
METRICS = 'system.load1'

def init_db():
    db = fdb.open()
    return db
    
@fdb.transactional
def set_dummy_metrics(tr):
    now = datetime.datetime.now()

    for minute in range(now.minute - 10, now.minute): # for the last 10 minutes of the hour
       for i in range(1, 12):
        seconds = i * 5 # set metric for every 5 second intervals
        tuple_key = monitoring.pack((MACHINE_ID,METRICS, now.year, now.month, now.day, now.hour, minute, seconds ))
        tr[tuple_key] = fdb.tuple.pack((random.uniform(2.533, 4.325), )) # set a random metric value and the timestamp of the metric


@fdb.transactional
def get_dummy_metrics(tr):
    print('Fetching dummy data..')
    for k, v in tr[monitoring.range()]:
        print(fdb.tuple.unpack(k) , '=>', fdb.tuple.unpack(v))

@fdb.transactional
def clear_db(tr):
    del tr[monitoring.range(())] #clear the directory        

if __name__ == '__main__':
   print('initializing fdb..')
   db = init_db()
   monitoring = fdb.directory.create_or_open(db, ('monitoring',))
   set_dummy_metrics(db)
