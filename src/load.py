import sys, codecs, json
from redis.client import Redis

db = Redis('localhost', 6379)

def load_dict(language, this_dict):
    infinitive = this_dict.keys()[0]
    infinitive_key = 'verb:%s:%s' % (language, infinitive)
    
    word_key = 'word:%s:%s' % (language, infinitive)
    db.set(word_key, json.dumps({'infinitive' : [infinitive]}))
    
    relations = json.loads(db.get(infinitive_key)) if db.exists(infinitive_key) else {}
    this_stack = [('', this_dict)]    
    first = True
    related_words = {}

    while this_stack != []:
        (prefix, this_dict) = this_stack.pop()
        # adds feminine participle to Spanish verb table (e.g. 'podrido' -> 'podrida')
        if language == 'es' and 'participle' in this_dict:
            this_dict['participle_feminine'] = [w[:-1] + 'a' for w in this_dict['participle']]
        if language == 'es' and prefix == 'imperative_' and 'second_person_plural_ustedes' in this_dict:
            this_dict['second_person_singular_usted'] = [w[:-1] for w in this_dict['second_person_plural_ustedes']]
        for key in this_dict:
            if type(this_dict[key]) is dict:
                if not first or key != infinitive:
                    this_stack.append((prefix + key + '_', this_dict[key]))
                else:
                    this_stack.append(('', this_dict[key]))
                    first = False
            elif type(this_dict[key]) is list:
                name = prefix + (key[1:] if key.startswith('*') else key)
                if not name in relations:
                    relations[name] = list()
                for elt in this_dict[key]:
                    if not elt in relations[name]:
                        relations[name].append(elt)
                    elt_key = 'word:%s:%s' % (language, elt)
                    if not elt_key in related_words:
                        related_words[elt_key] = json.loads(db.get(elt_key)) if db.exists(elt_key) else {}
                    elt_data = related_words[elt_key]
                    if not name in elt_data:
                        elt_data[name] = list()
                    if not infinitive in elt_data[name]:
                        elt_data[name].append(infinitive)
    
    for key, value in related_words.iteritems():
        db.set(key, json.dumps(value))
    db.set(infinitive_key, json.dumps(relations))

def load(language, ifile):
    count = 0
    for line in ifile:
        line = line.strip()
        if len(line) == 0: continue
        load_dict(language, json.loads(line))
        count += 1
        if count % 1000 == 0:
            print count, 'lines loaded...'

if __name__ == '__main__':
    fname = sys.argv[2]
    language = sys.argv[1]
    load(language, codecs.open(fname, 'r', 'utf-8'))