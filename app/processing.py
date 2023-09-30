import requests
import re
import time
import re
import spacy
from sklearn.feature_extraction.text import CountVectorizer
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from app.models import User, Commander, Deck, Card, Keyword, Card_keyword, Commander_collection, Deck_collection, Commander_gram
from datetime import datetime, timedelta

# I wanted to run my database to test some logic, but I need the flask app for the DB to launch, and I havnt hooked up the form yet.
from app import db

npl = spacy.load("en_core_web_sm")

class Processing():
    # This module is the heart of the card word processing and database inserts.
    # The scrape procedure goes: 
    # User requests card => Processing cleans the input, Checks if the card is in the database, calls to EDHrec to scrape for cards related (Check if cards have been scraped within X days) => Processing reformats the names, checks if the card is already in the database, calls Scryfall to fill in cards that aren't already there => While inserting, a connection should be made in Commander_collections =>

    def _clean_search_input(self, card_name,use):
        # 0 for EDH Rec end points, 1 (or anything) for Scryfall '+' joined for Scryfalls fuzzy search
        # print(card_name)
        if '//' in card_name:
            card_name = card_name.split('//')[0]
        card_name = card_name.replace("'", "")
        word_pat = re.compile("[A-Za-z]+")
        cleaned_input = re.findall(word_pat, card_name)
        if use == 0:
            return '-'.join(cleaned_input).lower()
        else:
            return '+'.join(cleaned_input).lower()

    def parseEDHrec_for_card_names(self, card_name, db = db):
        edh_cleaned_input_name = self._clean_search_input(card_name,0)

        # Leaving this here in case I get worried that I screwed up the timing.  Try 5 minutes and then 2 seconds.
        # if edh_cleaned_input_name == db.session.execute(db.select(Commander.search_name).where((Commander.search_name == edh_cleaned_input_name))).scalar() and datetime.now() - timedelta(seconds=2) < db.session.execute(db.select(Commander.last_scraped).where((Commander.search_name == edh_cleaned_input_name))).scalar():
        if edh_cleaned_input_name == db.session.execute(db.select(Commander.search_name).where((Commander.search_name == edh_cleaned_input_name))).scalar() and datetime.now() - timedelta(weeks=5) < db.session.execute(db.select(Commander.last_scraped).where((Commander.search_name == edh_cleaned_input_name))).scalar():

            print('You already have this card recently scraped')
            return None
        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
        url = f'https://edhrec.com/commanders/{self._clean_search_input(card_name,0)}'
        # driver.implicitly_wait(10)
        driver.get(url)
        time.sleep(3)

        if driver.find_elements(By.CLASS_NAME, 'page-heading')[0].text == 'Error 403':
            print('Could not find Commander.  Please check your spelling!')
            driver.close()
            return None
        # driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        y = 1000
        prev_pos = 0
        # I need to scroll through the page in order to load all the card tags so I can grab the card names.
        for timer in range(0,70):
            driver.execute_script("window.scrollTo(0, "+str(y)+")")
            
            current_scroll_height = driver.execute_script("return document.documentElement.scrollHeight")
            # This should break when the page gets to the bottom instead of going for the full 7
            # Selenium is a bit slow and laggy, so this only helps so much.
            if current_scroll_height < y:
                #print('breaking')
                break  

            y += 1000 
            # print('scrolling')
            time.sleep(.1)
            
        page_card_cont = []
        for i in driver.find_elements(By.TAG_NAME, 'a'):
            if i.get_attribute('href').split('/')[-2] == 'cards':
                page_card_cont.append(i.get_attribute('href').split('/')[-1])
        driver.close()
        # Add the commander to the list of card to pull. Need to also add a Database insert here!
        page_card_cont.append(self._clean_search_input(card_name,0))
        return set(page_card_cont)
    
    def insert_commander(self, card_name):
        search_name = self._clean_search_input(card_name,0)
        # print(db.session.execute(db.select(Commander.search_name).where((Commander.search_name == search_name))).scalar(), search_name)
        if search_name == db.session.execute(db.select(Commander.search_name).where((Commander.search_name == search_name))).scalar():
            # Update the last scraped column!
            commander_update = db.session.execute(db.select(Commander).where((Commander.search_name == search_name))).scalar()
            # db.session.get(Commander,db.session.execute(db.select(Commander).where((Commander.search_name == search_name))))
            #db.session.execute(db.select(Commander).where((Commander.search_name == search_name))).scalar()
            
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
                    # This means the card has already been connected to this commander in the past.
                    pass
                else:
                    commander_card = Commander_collection(commander_id=commander_id, card_id=card_id)
                    db.session.add(commander_card)
                    db.session.commit()

    
    def scryfall_check_and_retrieve(self,card,db):
        # Whenever I retrieve anything I should do this type of if statment to handle if The card already exsists in my db.
        if db.session.execute(db.select(Card).where(Card.search_name == card)).scalar(): 
                    print('I already have this card!')
                    pass
        # ALL THE DB STUFF NEEDS TO BE ADDED!
        else:
            scryfall_return = self.get_scryfall_json_data_fuzzy(card)
            # 'error' is the object return when there is an unscussesful full
            if scryfall_return.get('object') == 'error':
                print(f'Card {card} could not be found on Scryfall')
            else:
                print(f'Adding {card} to your database.')
                self.insert_card(scryfall_return, card)
                # Do a single card insert
            time.sleep(0.125)

    def edhrec_list_db_check_and_retrieve(self,card_list, commander,db = db):
        for card in card_list:
            self.scryfall_check_and_retrieve(card,db)
        self.insert_commander(commander)
        self.connect_commander_collection(commander, card_list)
        print('Done!')


    def get_scryfall_json_data_fuzzy(self, card_name):
        url=f'https://api.scryfall.com/cards/named?fuzzy={self._clean_search_input(card_name, 1)}'
        response = requests.get(url)
        j = response.json()
        return j
    
    def search_cards(self,card_request):
        clean_name = self._clean_search_input(card_request,1)
        url=f'https://api.scryfall.com/cards/search?q={clean_name}'
        # print(url)
        response = requests.get(url)
        j = response.json()
        cards = j.get('data')
        return cards
    
    def add_card_deckbuilder(self, scryfall_card, deck_id, db=db):
        if type(scryfall_card) == type('string'):
            clean_name = self._clean_search_input(scryfall_card,0)
        else:
            clean_name = self._clean_search_input(scryfall_card.get('name'),0)
        # print(clean_name)
        self.scryfall_check_and_retrieve(clean_name,db)
        requested_card_id = db.session.execute(db.select(Card.id).where(Card.search_name == clean_name)).scalar()
        # print(requested_card_id, deck_id)
        dc_card = Deck_collection(card_id=requested_card_id, deck_id=deck_id, is_commander=False, is_maindeck=True)
        db.session.add(dc_card)
        db.session.commit()

    def remove_card_deckbuilder(self, scryfall_card, deck_id, db=db):
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
        if scryfall_return.get('card_faces'):
            # Scrape multi_cardface cards (split cards, flip cards, whatever else)
            # print('Double faced card!')
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
                        
                    #print(card_name, search_name, oracle_text, type_line, power, toughness, mana_cost, cmc, color_identity, card_img)
                    # print('Hold your breath! Im trying to insert!')
                # So from here I need to deal with handling Colorless color_identities, Converting None to Null for nullable db inputs, 
                card = Card(card_name = card_name, search_name = search_name, oracle_text = oracle_text, type_line = type_line, power = power, toughness = toughness, mana_cost = mana_cost, cmc = cmc, color_identity = color_identity, card_img = card_img, double_sided_pointer = double_sided_pointer)
                db.session.add(card) 
                db.session.commit()
                # NOW I NEED TO DEAL WITH KEYWORDS! Things like Trample and Extort are in here, but also things like Treasure.  I might want to use some rules text for effects like extort for NLP.
                # Concat the two lists, (need to deal with Nones) loop through, check if the name is in keywords, if not add to keywords, then create connection between card ID and keyword.
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
                    # new_card_keyword = Card_keyword(keyword_id = db.session.execute(db.select(Keyword).where(Keyword.keyword_name == keyword)).scalar(),card_id = )
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
            #print(card_name, search_name, oracle_text, type_line, power, toughness, mana_cost, cmc, color_identity, card_img)
            # print('Hold your breath! Im trying to insert!')
        # So from here I need to deal with handling Colorless color_identities, Converting None to Null for nullable db inputs, 
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
                # new_card_keyword = Card_keyword(keyword_id = db.session.execute(db.select(Keyword).where(Keyword.keyword_name == keyword)).scalar(),card_id = )
                keyword_id = db.session.execute(db.select(Keyword.id).where(Keyword.keyword_name == keyword)).scalar()
                card_keyword_inst = Card_keyword(keyword_id=keyword_id, card_id=card_id)
                db.session.add(card_keyword_inst)
                db.session.commit()

    def find_meaning(self, commander_name, db=db):
        commander_name = self._clean_search_input(commander_name,0)
        commander_id = (db.session.execute(db.select(Commander.id).where(Commander.search_name == commander_name)).scalar())
        cards_ot = db.session.execute(db.select(Card.oracle_text).select_from(Card).join(Commander_collection, Card.id == Commander_collection.card_id).where(Commander_collection.commander_id == commander_id)).scalars().all()
        # print(cards_ot)
        cleaned_suggestions = []
        for card_inst in cards_ot:
            cleaned_suggestions.append(card_inst.replace('\n',' ').strip())
        oracle_body = ' '.join(cleaned_suggestions)
        # print(oracle_body)
        oracle_body = re.sub(r" on | the | of | to | and | with | in ","",oracle_body)
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
        commander_name = self._clean_search_input(commander_name,0)
        commander_id = db.session.execute(db.select(Commander.id).where(Commander.search_name == commander_name)).scalar()
        # print(commander_id)
        # commander_card_id = db.session.execute(db.select(Card.id).where(Card.search_name == commander_name)).scalar()
        # commander_grams = db.session.execute(
        #     db.select(Commander_gram)
        #     .select_from(Commander)
        #     .join(Commander_gram, Commander.id == Commander_gram.commander_id)
        #     .where(Commander_gram.commander_id == commander_id)
        # ).scalars().all()
        commander_grams = db.session.execute(
            db.select(Commander_gram, Commander)
            .where(Commander_gram.commander_id==commander_id)
            .join(Commander, Commander_gram.commander_id == Commander.id)).all()
        return_dict_list = []
        # print(commander_grams)
        for phrase in commander_grams:
            # print(phrase)
            grams = phrase[0].to_dict()
            card = phrase[1].to_dict()
            # print(card)
            return_dict = {
                "id":grams.get('id'),
                "n_gram":grams.get('n_gram'),
                "commander_id" :grams.get('commander_id'),
                "card_name":card.get('commander_name'),
                "card_img":card.get('card_img')
            }
            return_dict_list.append(return_dict)
        # commander_grams
    
        # commander_grams = db.session.execute(db.select(Commander_gram).select_from(Card).join(Card, Card.id == commander_card_id).where(Commander_gram.commander_id == commander_id)).scalars().all()

    #     result_list = [
    # {
    #     "id": commander_gram.id,
    #     "n_gram": commander_gram.n_gram,
    #     "n_count": commander_gram.n_count,
    #     "commander_id": commander_gram.commander_id,
    #     "card_name": card_name, 
    # }
    # for commander_gram, card_name in commander_grams]
        # print(commander_grams)
        return return_dict_list
    
    def deck_count(self, search_terms, deck_id):
        card_nums = db.session.execute(db.select(Deck_collection.card_id).where(Deck_collection.deck_id == deck_id)).scalars().all()
        cards_o_text = db.session.execute(
            db.select(Card.oracle_text).where(Card.id.in_(card_nums))
        ).scalars().all()
        deck_body = ' '.join(cards_o_text)
        # print(card_nums)
        # print(cards_o_text)
        # print(deck_body)
        return_dict_lst = []
        for term in search_terms:
            phrase = term.to_dict()
            instances = deck_body.count(phrase.get('search_term'))
            phrase['count'] = instances
            return_dict_lst.append(phrase)
        # print(return_dict_lst)
        return return_dict_lst
    
    



# check_function = Processing()
# ob_edhREC_list = check_function.parseEDHrec_for_card_names('Ob Nixilis, Captive Kingpin')
# check_function._clean_search_input('Ob Nixilis, Captain Kingpin',0)
# print(ob_edhREC_list)
# check_function.edhrec_list_db_check_and_retrieve(ob_edhREC_list)
# check_function.get_json_data_fuzzy("ob+nixilis+captive+kingpin")
# check_function.parseEDHrec_for_card_names('ob-nixilis-captive-kingpin')
# print(ob_edhREC_list[0])