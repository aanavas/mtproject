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
        ('(.*)_subjunctive_(.*)', '$infinitivexxsubjxx'),
        ('preterite(.*)', '$infinitivexxpastxx'),
        ('present_indicative_(.*)_plural', '$infinitive'),
        ('present_indicative_(first|second)_person_singular(.*)', '$infinitive'),
        ('present_indicative_third_person_singular(.*)', None),
        ('future_indicative(.*)', 'xxfutrxx $infinitive'),
        ('copreterite(.*)', '$infinitivexxcoprxx'),
        ('participle(.*)', '$infinitivexxpartxx'),
        ('imperative(.*)', '$infinitive'),
        ('conditional(.*)', 'xxcondxx $infinitive'),
    ], 'de': [
        ('past_participle', None),
        ('past(.*)', '$infinitivexxpastxx'),
        ('present_(.*)_plural', '$infinitive'),
        ('present_(first|second)_person_singular(.*)', '$infinitive'),
        ('present_third_person_singular(.*)', None),
        ('conditional_1(.*)', '$infinitivexxcnd1xx'),
        ('conditional_2(.*)', '$infinitivexxcnd2xx'),
        ('imperative(.*)', '$infinitive'),
    ], 'fr': [
    ]
}

PERSON = {
    'first_person_singular':    '1ps',
    'second_person_singular':   '2ps',
    'third_person_singular':    '3ps',
    'first_person_singular':    '1pp',
    'second_person_singular':   '2pp',
    'third_person_singular':    '3pp',
}

TESTS = {
    'es': {
           # should ignore nouns
           u'el camino es largo': u'el camino es largo',
           u'las fuerzas de seguridad': u'las fuerzas de seguridad',

           # present third-person-singular: unchanged
           u'ella camina al parque': u'ella camina al parque',
           
           # present everything-else: infinitive
           u'yo corro al parque': u'yo correr al parque',
           u'tú corres la carrera': u'tú correr la carrera',
           u'vosotros corréis al parque': u'vosotros correr al parque',
           u'nosotros comemos arroz': u'nosotros comer arroz',
           u'ellos caminan al parque': u'ellos caminar al parque',
           
           # future: xxfutrxx + infinitive
           u'la inflación saltará este año': u'la inflación xxfutrxx saltar este año',
           u'las finalistas se decidirán mañana': u'las finalistas se xxfutrxx decidir mañana',
           
           # past: infinitive+xxpastxx
           u'yo obtuve el primer lugar': u'yo obtenerxxpastxx el primer lugar',
           u'ellos ofrecieron sus disculpas': u'ellos ofrecerxxpastxx sus disculpas',
           u'nosotros usamos el carro de juan': u'nosotros usarxxpastxx el carro de juan',
           
           # copreterite: infinitive+xxcoprxx
           u'mientras conversaban con el director': u'mientras conversarxxcoprxx con el director',
           
           # participle: infinitive+xxpartxx
           u'todos se han contagiado': u'todos se haber contagiarxxpartxx',
           u'ella fue conducida a las autoridades': u'ella irxxpastxx conducirxxpartxx a las autoridades',
           
           # subjunctive: infinitive+xxsubjxx
           u'quieres que te cuente o no ?': u'querer que te contarxxsubjxx o no ?',
           u'ellos me dijeron que no te dijera nada': u'ellos me decirxxpastxx que no te decirxxsubjxx nada',
           
           # imperative
           u'ten tus cosas': 'tener tus cosas',
           
           # conditional
           u'me gustaría ayudarte': u'me xxcondxx gustar ayudarte',
           u'ellos podrían venir más temprano': u'ellos xxcondxx poder venir más temprano',
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
    
def render_tokens(token, replacement, infinitives, person_token=None):
    value = token
    if replacement is not None:
        value = replacement.replace('$infinitive', infinitives[0])
    return person_token + ' ' + value if person_token else value

def transform_token(language, token, pos_tag, person=True):
    word = get_word(language, token, pos_tag)
    if word is not None:
        for rule, replacement in RULES[language]:
            for conjugation, infinitives in word.iteritems():
                if re.compile(rule).match(conjugation):
                    person_token = None
                    if person:
                        for key, value in PERSON.iteritems():
                            if key in conjugation:
                                person_token = 'xx%sxx' % value
                                break
                    return render_tokens(token, replacement, infinitives, person_token)
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