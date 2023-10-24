import requests
import re
import time
import re
import spacy
from sklearn.feature_extraction.text import CountVectorizer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager
from app.models import User, Commander, Deck, Card, Keyword, Card_keyword, Commander_collection, Deck_collection, Commander_gram
from datetime import datetime, timedelta


from app import db

npl = spacy.load("en_core_web_sm")

class Processing():
    '''
    This module is the heart of the card word processing and database inserts.
    The scrape procedure goes: 
    Admin/User requests card => Processing cleans the input, Checks if the card is in the database, {if admin} calls to EDHrec to scrape for cards related (Check if cards have been scraped within X days) => Processing reformats the names, checks if the card is already in the database, calls Scryfall to fill in cards that aren't already there => While inserting, a connection should be made in Commander_collections => Does NLP and saves to database => {if user} Shows the common lemmatized n_gram. 
    '''

    def _clean_search_input(self, card_name,use):
        # 0 for EDH Rec end points, 1 (or anything) for Scryfall '+' joined for Scryfalls fuzzy search
        if '//' in card_name:
            card_name = card_name.split('//')[0]
        card_name = card_name.replace("'", "")
        word_pat = re.compile("[A-Za-z]+")
        cleaned_input = re.findall(word_pat, card_name)
        if use == 0:
            return '-'.join(cleaned_input).lower()
        else:
            return '+'.join(cleaned_input).lower()
    
    
    def insert_commander(self, card_name):
        # Checks if commander is in db.  If not, add them.
        search_name = self._clean_search_input(card_name,0)
        if search_name == db.session.execute(db.select(Commander.search_name).where((Commander.search_name == search_name))).scalar():
            commander_update = db.session.execute(db.select(Commander).where((Commander.search_name == search_name))).scalar()            
            setattr(commander_update,'last_scraped',datetime.now())
            db.session.commit()
        else:
            commander = db.session.execute(db.select(Card).where((Card.search_name == search_name))).scalar()
            commander_name = commander.card_name
            card_img = commander.card_img
            commander = Commander(commander_name=commander_name, search_name=search_name, card_img=card_img, last_scraped=datetime.now())
            db.session.add(commander)
            db.session.commit()

    def connect_commander_collection(self, commander, card_collection):
        search_name = self._clean_search_input(commander,0)
        commander_id = db.session.execute(db.select(Commander.id).where(Commander.search_name == search_name)).scalar()
        for card in card_collection:
            card_id = db.session.execute(db.select(Card.id).where(Card.search_name == card)).scalar()
            if card_id:
                if db.session.execute(db.select(Commander_collection).where((Commander_collection.card_id == card_id) & (Commander_collection.commander_id == commander_id))).scalar():
                    pass
                else:
                    commander_card = Commander_collection(commander_id=commander_id, card_id=card_id)
                    db.session.add(commander_card)
                    db.session.commit()

    
    def scryfall_check_and_retrieve(self,card,db):
        # Check if I have the card and then get it from scryfall if I dont.
        if db.session.execute(db.select(Card).where(Card.search_name == card)).scalar(): 
                    print('I already have this card!')
                    pass
        else:
            scryfall_return = self.get_scryfall_json_data_fuzzy(card)
            if scryfall_return.get('object') == 'error':
                print(f'Card {card} could not be found on Scryfall')
            else:
                print(f'Adding {card} to your database.')
                self.insert_card(scryfall_return, card)
                # Do a single card insert
            time.sleep(0.125)

    def edhrec_list_db_check_and_retrieve(self,card_list, commander,db = db):
        # Loops through list of cards retrieved from EDHrec
        for card in card_list:
            self.scryfall_check_and_retrieve(card,db)
        self.insert_commander(commander)
        self.connect_commander_collection(commander, card_list)
        print('Done!')


    def get_scryfall_json_data_fuzzy(self, card_name):
        # Do fuzzy search on scryfall
        url=f'https://api.scryfall.com/cards/named?fuzzy={self._clean_search_input(card_name, 1)}'
        response = requests.get(url)
        j = response.json()
        return j
    
    def search_cards(self,card_request):
        # Do search for exact card name from EDHrec
        clean_name = self._clean_search_input(card_request,1)
        url=f'https://api.scryfall.com/cards/search?q={clean_name}'
        # print(url)
        response = requests.get(url)
        j = response.json()
        cards = j.get('data')
        return cards
    
    def add_card_deckbuilder(self, scryfall_card, deck_id, db=db):
        # add card to deck
        if type(scryfall_card) == type('string'):
            clean_name = self._clean_search_input(scryfall_card,0)
        else:
            clean_name = self._clean_search_input(scryfall_card.get('name'),0)
        self.scryfall_check_and_retrieve(clean_name,db)
        requested_card_id = db.session.execute(db.select(Card.id).where(Card.search_name == clean_name)).scalar()
        dc_card = Deck_collection(card_id=requested_card_id, deck_id=deck_id, is_commander=False, is_maindeck=True)
        db.session.add(dc_card)
        db.session.commit()

    def remove_card_deckbuilder(self, scryfall_card, deck_id, db=db):
        # Remove card from a deck
        if type(scryfall_card) == type('string'):
            clean_name = self._clean_search_input(scryfall_card,0)
        else:
            clean_name = self._clean_search_input(scryfall_card.get('name'),0)
        self.scryfall_check_and_retrieve(clean_name,db)
        requested_card_id = db.session.execute(db.select(Card.id).where(Card.search_name == clean_name)).scalar()
        card_entry = db.session.execute(db.select(Deck_collection).where((Deck_collection.deck_id==deck_id) & (Deck_collection.card_id==requested_card_id))).scalar()
        if card_entry:
            db.session.delete(card_entry)
            db.session.commit()

    def insert_card(self, scryfall_return, search_name):
        # Insert card from Scryfall.
        # Lots of ternary due to the multiple shapes of data that the cards can be in
        if scryfall_return.get('card_faces'):
            for i, card_half in enumerate(scryfall_return.get('card_faces')):
                if card_half.get('image_uris'):
                    card_name = card_half.get('name')
                    search_name = self._clean_search_input(card_name,0)
                    oracle_text = card_half.get('oracle_text')
                    type_line = card_half.get('type_line')
                    power = card_half.get('power')
                    if power:
                        try:
                            power = int(power)
                        except:
                            power = 0
                    toughness = card_half.get('toughness')
                    if toughness:
                        try:
                            toughness = int(toughness)
                        except:
                            toughness = 0
                    mana_cost = card_half.get('mana_cost')
                    cmc = card_half.get('cmc')
                    if cmc:
                        cmc = float(cmc)
                    else:
                        cmc = 0
                    try:
                        color_identity = ''.join(card_half.get('color_identity'))
                    except:
                        color_identity = ''.join(scryfall_return.get('color_identity'))
                    card_img = card_half.get('image_uris').get('border_crop' )
                    # Create a link between the primary card and any others
                    if i == 0:
                        double_sided_pointer = self._clean_search_input(scryfall_return.get('card_faces')[1].get('name'),0)
                    else:
                        double_sided_pointer = self._clean_search_input(scryfall_return.get('card_faces')[0].get('name'),0)
                    # make keyword list - There can be both card level and face level keywords that need to be tracked...
                    card_level_keywords = scryfall_return.get('keywords')
                    side_level_keywords = card_half.get('keywords')
                    
                else:
                    card_name = card_half.get('name')
                    search_name = self._clean_search_input(card_name,0)
                    oracle_text = card_half.get('oracle_text')
                    type_line = card_half.get('type_line')
                    power = card_half.get('power')
                    if power:
                        try:
                            power = int(power)
                        except:
                            power = 0
                    toughness = card_half.get('toughness')
                    if toughness:
                        try:
                            toughness = int(toughness)
                        except:
                            toughness = 0
                    mana_cost = card_half.get('mana_cost')
                    cmc = card_half.get('cmc')
                    if cmc:
                        cmc = float(cmc)
                    else:
                        cmc = 0
                    try:
                        color_identity = ''.join(card_half.get('color_identity'))
                    except:
                        color_identity = ''.join(scryfall_return.get('color_identity'))
                    card_img = scryfall_return.get('image_uris').get('border_crop' )
                    if i == 0:
                        double_sided_pointer = self._clean_search_input(scryfall_return.get('card_faces')[1].get('name'),0)
                    else:
                        double_sided_pointer = self._clean_search_input(scryfall_return.get('card_faces')[0].get('name'),0)
                    card_level_keywords = scryfall_return.get('keywords')
                    side_level_keywords = card_half.get('keywords')
                card = Card(card_name = card_name, search_name = search_name, oracle_text = oracle_text, type_line = type_line, power = power, toughness = toughness, mana_cost = mana_cost, cmc = cmc, color_identity = color_identity, card_img = card_img, double_sided_pointer = double_sided_pointer)
                db.session.add(card) 
                db.session.commit()
                if card_level_keywords == None:
                    card_level_keywords = []
                if side_level_keywords == None:
                    side_level_keywords = []
                card_id = db.session.execute(db.select((Card.id)).where(Card.search_name == search_name)).scalar()
                for keyword in card_level_keywords + side_level_keywords:
                    if not db.session.execute(db.select(Keyword).where(Keyword.keyword_name == keyword)).scalar():
                        new_keyword = Keyword(keyword_name=keyword)
                        db.session.add(new_keyword)
                        db.session.commit()
                    keyword_id = db.session.execute(db.select(Keyword.id).where(Keyword.keyword_name == keyword)).scalar()
                    card_keyword_inst = Card_keyword(keyword_id=keyword_id, card_id=card_id)
                    db.session.add(card_keyword_inst)
                    db.session.commit()
        else:
            card_name = scryfall_return.get('name')
            search_name = search_name
            oracle_text = scryfall_return.get('oracle_text')
            type_line = scryfall_return.get('type_line')
            power = scryfall_return.get('power')
            if power:
                try:
                    power = int(power)
                except:
                    power = 0
            toughness = scryfall_return.get('toughness')
            if toughness:
                try:
                    toughness = int(toughness)
                except:
                    toughness = 0
            mana_cost = scryfall_return.get('mana_cost')
            cmc = int(scryfall_return.get('cmc'))
            color_identity = ''.join(scryfall_return.get('color_identity'))
            card_img = scryfall_return.get('image_uris').get('border_crop' )
            keywords = scryfall_return.get('keywords')
            card = Card(card_name = card_name, search_name = search_name, oracle_text = oracle_text, type_line = type_line, power = power, toughness = toughness, mana_cost = mana_cost, cmc = cmc, color_identity = color_identity, card_img = card_img)
            db.session.add(card) 
            db.session.commit()
            if keywords == None:
                keywords = []
            card_id = db.session.execute(db.select(Card.id).where(Card.search_name == search_name)).scalar()
            for keyword in keywords:
                if not db.session.execute(db.select(Keyword).where(Keyword.keyword_name == keyword)).scalar():
                    new_keyword = Keyword(keyword_name=keyword)
                    db.session.add(new_keyword)
                    db.session.commit()
                keyword_id = db.session.execute(db.select(Keyword.id).where(Keyword.keyword_name == keyword)).scalar()
                card_keyword_inst = Card_keyword(keyword_id=keyword_id, card_id=card_id)
                db.session.add(card_keyword_inst)
                db.session.commit()

    def find_meaning(self, commander_name, db=db):
        # This is where I create and count my n_grams.  It is very basic, but it has shown a few cool things.  Its good with commanders that are 'on the rails'.
        commander_name = self._clean_search_input(commander_name,0)
        commander_id = (db.session.execute(db.select(Commander.id).where(Commander.search_name == commander_name)).scalar())
        cards_ot = db.session.execute(db.select(Card.oracle_text).select_from(Card).join(Commander_collection, Card.id == Commander_collection.card_id).where(Commander_collection.commander_id == commander_id)).scalars().all()
        cleaned_suggestions = []
        for card_inst in cards_ot:
            cleaned_suggestions.append(card_inst.replace('\n',' ').strip())
        oracle_body = ' '.join(cleaned_suggestions)
        oracle_body = re.sub(r"the |of |to |and |with |in ","",oracle_body)
        doc = npl(oracle_body)
        lemmas = []
        for token in doc:
            if not token.is_punct:
                lemmas.append(token.lemma_)
        lemetized_oracle = ' '.join(lemmas)   
        v = CountVectorizer(ngram_range=(2,3), token_pattern=r'(?u)\b[\d\w]+\b')
        v.fit([lemetized_oracle])
        vocab = v.vocabulary_  
        for phrase in vocab:
            insts = lemetized_oracle.count(phrase)
            if insts > 40 and insts < 100:
                if db.session.execute(db.select(Commander_gram).where((Commander_gram.commander_id == commander_id) & (Commander_gram.n_gram == phrase))).scalar():
                    pass
                else:
                    commander_gram = Commander_gram(n_gram = phrase, n_count = insts, commander_id = commander_id)
                    db.session.add(commander_gram)
                    db.session.commit()
    
    def retrieve_commandergrams(self, commander_name, db=db):
        # DB query to get commandergrams
        commander_name = self._clean_search_input(commander_name,0)
        commander_id = db.session.execute(db.select(Commander.id).where(Commander.search_name == commander_name)).scalar()
        commander_grams = db.session.execute(
            db.select(Commander_gram, Commander)
            .where(Commander_gram.commander_id==commander_id)
            .join(Commander, Commander_gram.commander_id == Commander.id)).all()
        return_dict_list = []
        for phrase in commander_grams:
            grams = phrase[0].to_dict()
            card = phrase[1].to_dict()
            return_dict = {
                "id":grams.get('id'),
                "n_gram":grams.get('n_gram'),
                "commander_id" :grams.get('commander_id'),
                "card_name":card.get('commander_name'),
                "card_img":card.get('card_img')
            }
            return_dict_list.append(return_dict)
        return return_dict_list
    
    def deck_count(self, search_terms, deck_id):
        # Does the 'how many times does "deal 1" happen'
        card_nums = db.session.execute(db.select(Deck_collection.card_id).where(Deck_collection.deck_id == deck_id)).scalars().all()
        cards_o_text = db.session.execute(
            db.select(Card.oracle_text).where(Card.id.in_(card_nums))
        ).scalars().all()
        deck_body = ' '.join(cards_o_text)
        return_dict_lst = []
        for term in search_terms:
            phrase = term.to_dict()
            instances = deck_body.count(phrase.get('search_term'))
            phrase['count'] = instances
            return_dict_lst.append(phrase)
        return return_dict_lst