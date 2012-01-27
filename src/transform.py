# -*- coding: utf-8 -*-

import sys
import json
import re
from redis.client import Redis
import urllib
import urllib2
import hashlib

RULES = {
    'es': [
        ('future_indicative(.*)', 'xxfutrxx $infinitive'),
        ('present_indicative_(.*)_plural', '$infinitive'),
        ('present_indicative_(first|second)_person_singular(.*)', '$infinitive')
    ]
}

TESTS = {
    'es': {
           u'la inflación saltará este año': u'la inflación xxfutrxx saltar este año',
           u'yo camino al parque': u'yo caminar al parque',
           u'tú caminas al parque': u'tú caminar al parque',
           u'ella camina al parque': u'ella camina al parque',
           u'vosotros camináis al parque': u'vosotros caminar al parque',
           u'nosotros caminamos al parque': u'nosotros caminar al parque',
           u'ellos caminan al parque': u'ellos caminar al parque',
           u'el camino es largo': u'el camino es largo',
    }
}

db = Redis('localhost', 6379)

DICTIONARY_HOST = 'blue4.monolingo.cs.cmu.edu:8081'

def get_response(url, params):
    url_GET = url + '?%s' % (params)
    if len(url_GET) > 4096:  # uses POST
        f = urllib2.urlopen(url, params)
    else:                    # uses GET
        f = urllib2.urlopen(url_GET)
    return f.read()

def get_pos_tagger(language, sentence, universal_tags=True, tuning=False):
    try:
        params = urllib.urlencode({
                'sentence': sentence.encode('utf-8'),
                'utags': universal_tags,
                'tuning': tuning})
        url = 'http://%s/words/postag/%s' % (DICTIONARY_HOST, language)
        return json.loads(get_response(url, params))
    except Exception as e:
        print "ERROR:", e, url
        return None
    
def get_pos_tags(language, sentence):
    hash_function = hashlib.md5()
    hash_function.update(language)
    hash_function.update(sentence.encode('utf-8'))
    key = 'pos:%s' % hash_function.hexdigest()
    
    if db.exists(key):
        return json.loads(db.get(key))
    else:
        result = get_pos_tagger(language, sentence)
        db.set(key, json.dumps(result))
        return result

def get_word(language, word, pos_tag):
    if pos_tag[0]==word and pos_tag[1] != 'VERB': return None
    word_key = 'word:%s:%s' % (language, word)
    data = db.get(word_key)
    if data is None: return None
    else: return json.loads(data)
    
def render_tokens(replacement, infinitives):
    return replacement.replace('$infinitive', infinitives[0])

def transform_token(language, token, pos_tag):
    word = get_word(language, token, pos_tag)
    if word is not None:
        for rule, replacement in RULES[language]:
            for conjugation, infinitives in word.iteritems():
                if re.compile(rule).match(conjugation):
                    return render_tokens(replacement, infinitives)
    return token

def transform(language, sentence):
    pos_tags = get_pos_tags(language, sentence)
    return ' '.join([transform_token(language, t, pos_tags[i]) for i, t in enumerate(sentence.split())])

if __name__ == '__main__':
    language = sys.argv[1]
    for test in TESTS[language]:
        transformed = transform(language, test)
        if transformed != TESTS[language][test]:
            print 'ERROR:', test, '=>', transformed, '!=', TESTS[language][test]