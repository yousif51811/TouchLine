import re
import unicodedata

BANK={
    'en':['apple','banana','orange','dates','bread','milk','rice','water'],
    'ar':['تفاح','موز','برتقال','تمر','خبز','حليب','أرز','ماء'],
}
CARDS={
    'en':[{'required':['pass','shoot','goal'],'forbidden':'foul'},
          {'required':['team','win','trophy'],'forbidden':'lose'},
          {'required':['run','kick','score'],'forbidden':'stop'}],
    'ar':[{'required':['تمريرة','تسديدة','هدف'],'forbidden':'خطأ'},
          {'required':['فريق','فوز','كأس'],'forbidden':'خسارة'},
          {'required':['جري','ركلة','نتيجة'],'forbidden':'توقف'}],
}
ALIASES={'apples':'apple','bananas':'banana','oranges':'orange','date':'dates',
         'passes':'pass','passed':'pass','passing':'pass','shoots':'shoot','shooting':'shoot',
         'goals':'goal','teams':'team','wins':'win','trophies':'trophy','runs':'run','kicks':'kick',
         'scores':'score','تمريره':'تمريرة','تسديده':'تسديدة','ركله':'ركلة','نتيجه':'نتيجة'}

def normalize(text):
    text=unicodedata.normalize('NFKC',text).lower()
    text=''.join(c for c in text if not unicodedata.combining(c) and c!='ـ')
    text=text.translate(str.maketrans({'أ':'ا','إ':'ا','آ':'ا','ٱ':'ا','ى':'ي'}))
    return re.findall(r'[^\W\d_]+',text,re.UNICODE)

NORMAL_ALIASES={normalize(k)[0]:normalize(v)[0] for k,v in ALIASES.items()}
def tokens(text):
    return [NORMAL_ALIASES.get(t,t) for t in normalize(text)]

def score_souq(text,basket,language):
    spoken=tokens(text)
    expected=[tokens(item)[0] for item in basket]
    allowed={tokens(item)[0]:item for item in BANK[language]}
    repetition=bool(spoken) and len(spoken)>=len(expected) and spoken[:len(expected)]==expected
    addition=len(spoken)==len(expected)+1 and spoken[-1] in allowed and spoken[-1] not in expected
    accepted=repetition and addition
    checks=[{'key':'sequence','passed':repetition,'points':int(repetition)},
            {'key':'new_item','passed':addition,'points':int(addition)}]
    return {'points':sum(c['points'] for c in checks),'maximum':2,'checks':checks,
            'basket':basket+[allowed[spoken[-1]]] if accepted else list(basket)}

def score_mic(text,card):
    spoken=tokens(text)
    required=[tokens(word)[0] for word in card['required']]
    indices=[spoken.index(word) if word in spoken else -1 for word in required]
    ordered=all(i>=0 for i in indices) and indices==sorted(indices)
    avoided=bool(spoken) and tokens(card['forbidden'])[0] not in spoken
    checks=[{'key':'required','word':word,'passed':i>=0,'points':int(i>=0)} for word,i in zip(card['required'],indices)]
    checks.extend([{'key':'order','passed':ordered,'points':int(ordered)},
                   {'key':'forbidden','passed':avoided,'points':int(avoided)}])
    return {'points':sum(c['points'] for c in checks),'maximum':5,'checks':checks}
