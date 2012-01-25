# -*- coding: utf-8 -*-

import sys
import redis
#import simplejson as json
import json as json
from transform import transform

SUFFIX = {
    'FPS':  '1ps',
    'SPST': '2ps',
    'SPSV': '2ps',
    'SPSU': '2ps',
    'TPS':  '3ps',
    'FPP':  '1pp',
    'SPPV': '2pp',
    'SPPU': '2pp',
    'TPP':  '3pp'
}

ES_ACCENT_DROP = {u'á': u'a', u'é': u'e', u'í': u'i', u'ó': u'o', u'ú': u'u',
                  u'Á': u'A', u'É': u'E', u'Í': u'I', u'Ó': u'O', u'Ú': u'U'}
ES_VERB_SUFFIX = [] #"lo", "la", "le", "los", "las", "les", "me", "te", "se", "nos"]

def drop_accents(word):
    new_word = []
    for letter in word:
        if letter in ES_ACCENT_DROP:
            new_word.append(ES_ACCENT_DROP[letter])
        else:
            new_word.append(letter)
    return ''.join(new_word)

class Analyzer:
    def __init__(self, language):
        self.r = redis.Redis('blue4.monolingo.cs.cmu.edu', 6379)
        self.language = language

    def get_clitics(self, word):
        result = []
        for ending in ES_VERB_SUFFIX:
            if word.endswith(ending):
                try_word = left = word[:-len(ending)].lower()
                data = self.r.get('Token:%s|' % self.language + try_word.encode('utf-8') + ':object')
                if data is not None: data = json.loads(data)
                if data is not None and (('conjugated_of' in data and data['conjugated_of']) or ('conjugations' in data and data['conjugations'])):
                    result.append(try_word)
                else:
                    for i in range(0, len(try_word)):
                        if try_word[i] in ES_ACCENT_DROP:
                            try_word = try_word[:i]+ES_ACCENT_DROP[try_word[i]]+try_word[i+1:]
                            data = self.r.get('Token:%s|' % self.language + try_word.encode('utf-8') + ':object')
                            if data is not None: data = json.loads(data)
                            if data is not None and (('conjugated_of' in data and data['conjugated_of']) or ('conjugations' in data and data['conjugations'])):
                                result.append(try_word)
                                break
                if len(result) == 0:
                    temp_result = self.get_clitics(left)
                    if len(temp_result) == 1:
                        continue
                    result += temp_result
                result.append(ending)
                return result
        return [word]

    def analyze(self, token):
        meanings = self.r.scard('Meaning:token=es|' + token.encode('utf-8') + ':index')
        if meanings>0: return token

        singular = None
        if len(token)>4 and token.endswith('es'):
            singular = token[:-2]
        elif len(token)>3 and token.endswith('s'):
            singular = token[:-1]
    
        if singular:
            meanings = self.r.scard('Meaning:token=es|' + singular.encode('utf-8') + ':index')
            if meanings>0: return token
            
            if singular.endswith('on'): singular = singular[:-2] + u'ón'
            meanings = self.r.scard('Meaning:token=es|' + singular.encode('utf-8') + ':index')
            if meanings>0: return token      

        #clitics = []
        data = self.r.get('Token:%s|' % self.language + token.encode('utf-8') + ':object')
        #if data is None: clitics = self.get_clitics(token)
        #if len(clitics) > 0:
        #    token = clitics[0]
        #    clitics = clitics[1:]
        #else:
        #    clitics = []

        #if data is None: data = self.r.get('Token:%s|' % self.language + token.encode('utf-8') + ':object')
        if data is None: return token
        data = json.loads(data)
        if 'conjugated_of' not in data: return token
        
        conjugations = data['conjugated_of']
        all_conjs = set()
        all_verbs = set()
        all_person = set()
        attached = False
        present = False

        for conj, verbs in conjugations.iteritems():
            if 'ser' in verbs or 'estar' in verbs:
                return token
            for verb in verbs:
                all_verbs.add(verb)
            info = conj.split('_')
            infor = ''.join([x[0].upper() for x in info])
            if conj == 'gerund' or conj.startswith('participle'):
                return token
            if 'imperativ' in conj or 'subjunctive' in conj:
                if info[0] == 'preterite':
                    all_conjs.add('past')
                    attached = True
                else:
                    pass
            elif 'indicative' in conj:
                if info[0] == 'conditional':
                    all_conjs.add('cond')
                elif info[0] == 'future':
                    all_conjs.add('futr')
                elif info[0] == 'copreterite':
                    all_conjs.add('past')
                    attached = True
                elif info[0] == 'preterite':
                    all_conjs.add('past')
                    attached = True
                elif info[0] == 'present':
                    present = True
            elif 'past' in conj:
                all_conjs.add('past')
                attached = True              
            elif 'conditional' in conj:
                all_conjs.add('cond')            

            for suff, person in SUFFIX.iteritems():
                if infor.endswith(suff):
                    all_person.add(person)

        if len(all_verbs) != 1: return token

        ckey = 'xx' + 'xx'.join(sorted(list(all_conjs))) + 'xx' if len(all_conjs)>0 else None
        pkey = 'xx' + 'xx'.join(sorted(list(all_person))) + 'xx' if len(all_person)>0 else None
 
        morphemes = []
        #if pkey: morphemes.append(pkey)
        if ckey and not attached and not present: morphemes.append(ckey)
        
        verb = all_verbs.pop()
        if ckey and attached and not present: verb += ckey
        if present and '3ps' in pkey: verb += 'xx3psxx'
        morphemes.append(verb)

        #if clitics != []:
        #    morphemes += ['xx'+cl+'xx' for cl in clitics]

        return ' '.join(morphemes)

    def process(self, tokens):
        return ' '.join([self.analyze(t) for t in tokens])

if __name__ == '__main__':
    #analyzer = Analyzer(sys.argv[1])
    language = sys.argv[1]
    line = sys.stdin.readline()
    while line:
        line = unicode(line, 'utf-8')
        #print analyzer.process(line.strip().split()).encode('utf-8')
        print transform(language, line.strip()).encode('utf-8')
        line = sys.stdin.readline()
