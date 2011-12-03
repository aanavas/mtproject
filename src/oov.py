# -*- coding: utf-8 -*-

import sys
import redis
import simplejson as json

SUFFIX = {
    'FPS':  '1ps',
    'SPST': '2ps',
    'SPSV': '2ps',
    'SPSU': '2ps',
    'TPS':  '3ps',
    'FPP':  '1pp',
    'SPPV': '2pp',
    'SPPU': '2pp',
    'TPP': '3pp'
}

ES_ACCENT_DROP = {u'á': u'a', u'é': u'e', u'í': u'i', u'ó': u'o', u'ú': u'u',
                  u'Á': u'A', u'É': u'E', u'Í': u'I', u'Ó': u'O', u'Ú': u'U'}
ES_VERB_SUFFIX = ["lo", "la", "le", "los", "las", "les", "me", "te", "se", "nos"]

class Analyzer:
    def __init__(self):
        self.r = redis.Redis('blue4.monolingo.cs.cmu.edu', 6379)
        self.verbs = list()
        self.words = list()

    def get_clitics(self, word):
        result = []
        for ending in ES_VERB_SUFFIX:
            if word.endswith(ending):
                try_word = left = word[:-len(ending)].lower()
                data = self.r.get('Token:es|' + try_word.encode('utf-8') + ':object')
                if data is not None: data = json.loads(data)
                if data is not None and ('conjugated_of' in data or 'conjugations' in data):
                    result.append(try_word)
                else:
                    for i in range(0, len(try_word)):
                        if try_word[i] in ES_ACCENT_DROP:
                            try_word = try_word[:i]+ES_ACCENT_DROP[try_word[i]]+try_word[i+1:]
                            data = self.r.get('Token:es|' + try_word.encode('utf-8') + ':object')
                            if data is not None: data = json.loads(data)
                            if data is not None and ('conjugated_of' in data or 'conjugations' in data):
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
        if meanings>0: return False

        singular = None
        if len(token)>4 and token.endswith('es'):
            singular = token[:-2]
        elif len(token)>3 and token.endswith('s'):
            singular = token[:-1]
    
        if singular:
            meanings = self.r.scard('Meaning:token=es|' + singular.encode('utf-8') + ':index')
            if meanings>0: return False

        data = self.r.get('Token:es|' + token.encode('utf-8') + ':object')
        clitics = []
        if data is None: clitics = self.get_clitics(token)
        if len(clitics) > 0:
            token = clitics[0]

        if data is None: data = self.r.get('Token:es|' + token.encode('utf-8') + ':object')
        if data is None: return False
        data = json.loads(data)
        return (('conjugated_of' in data and data['conjugated_of']) or
                ('conjugation' in data and data['conjugation']))

    def process(self, tokens, lu, lv):
        for token in tokens:
            if '|UNK' in token:
                lu += 1
                token = token.split('|')[0]
                if self.analyze(token): 
                    lv += 1
                    self.verbs.append(token)
                self.words.append(token)
        return (lu, lv)

if __name__ == '__main__':
    analyzer = Analyzer()
    line = sys.stdin.readline()
    unk = 0
    vrb = 0
    cnt = 0
    while line:
        if not line.startswith('BEST TRANSLATION'): 
            line = sys.stdin.readline()
            continue
        line = unicode(line, 'utf-8').strip()
        tokens = []
        for token in line.strip().split()[2:]:
            if token.startswith('['): break
            tokens.append(token)
        cnt += len(tokens)
        if '|UNK|UNK|UNK' in line:
            (unk, vrb) = analyzer.process(line.strip().split(), unk, vrb)
        line = sys.stdin.readline()
    print unk, vrb, unk*100.0/cnt, vrb*100.0/unk
    #print 'verbs:\n', '\n'.join(sorted(analyzer.verbs)).encode('utf-8')

