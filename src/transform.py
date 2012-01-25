# -*- coding: utf-8 -*-

import sys
import json
import re
from redis.client import Redis

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
    }
}

db = Redis('localhost', 6379)

def get_word(language, word):
    word_key = 'word:%s:%s' % (language, word)
    data = db.get(word_key)
    if data is None: return None
    else: return json.loads(data)
    
def render_tokens(replacement, infinitives):
    return replacement.replace('$infinitive', infinitives[0])

def transform_token(language, token):
    word = get_word(language, token)
    if word is not None:
        for rule, replacement in RULES[language]:
            for conjugation, infinitives in word.iteritems():
                if re.compile(rule).match(conjugation):
                    return render_tokens(replacement, infinitives)
    return token

def transform(language, sentence):
    return ' '.join([transform_token(language, t) for t in sentence.split()])

if __name__ == '__main__':
    language = sys.argv[1]
    for test in TESTS[language]:
        transformed = transform(language, test)
        if transformed != TESTS[language][test]:
            print 'ERROR:', test, transformed, '!=', TESTS[language][test]