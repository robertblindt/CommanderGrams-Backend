import os
import base64
from app import db, login
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin



class User(db.Model, UserMixin):#, UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    first_name = db.Column(db.String(50), nullable = False)
    last_name = db.Column(db.String(50), nullable = False)
    email = db.Column(db.String(75), nullable = False, unique = True )
    username = db.Column(db.String(50), nullable = False, unique = True)
    password = db.Column(db.String, nullable = False)
    date_created = db.Column(db.DateTime, nullable = False, default = datetime.utcnow)
    token = db.Column(db.String(32), index = True, unique = True)
    token_expiration = db.Column(db.DateTime)

    def __init__(self,**kwargs):
        super().__init__(**kwargs)
        self.password = generate_password_hash(kwargs.get('password'))

    def __repr__(self):
        return f"<User {self.id}|{self.username}>"

    def check_password(self, password_guess):
        return check_password_hash(self.password, password_guess)
    
    def get_token(self, expires_in = 36000):
        now = datetime.utcnow()
        if self.token and self.token_expiration > now + timedelta(seconds = 60):
            return self.token
        self.token = base64.b64encode(os.urandom(24)).decode('utf-8')
        self.token_expiration = now + timedelta(seconds = expires_in)
        db.session.commit()
        return self.token

    def revoke_token(self):
        self.token_expiration = datetime.utcnow() - timedelta(seconds=1)
        db.session.commit()
    

    def to_dict(self):
        return {
            'id': self.id,
            'first_name': self.first_name,
            'last_name': self.last_name,
            'email': self.email,
            'username': self.username
        }


@login.user_loader
def load_user(user_id):
    return db.session.get(User, user_id)

class Commander(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    commander_name = db.Column(db.String(100), nullable = False)
    search_name = db.Column(db.String(100), nullable = False)
    card_img = db.Column(db.String, nullable = False)
    last_scraped = db.Column(db.DateTime, nullable = False, default = datetime.utcnow)
    
    def __repr__(self):
        return f"<Deck {self.id}|{self.commander_name}|{self.last_scraped}>"
    
    def to_dict(self):
        return {
            'id' : self.id,
            'commander_name' : self.commander_name,
            'card_img': self.card_img,
            'last_scraped' : self.last_scraped
        }



class Deck(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    deck_name = db.Column(db.String(50), nullable = False)
    description = db.Column(db.String, nullable = True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable = False)
    cards = db.relationship('Deck_collection', backref = 'Deck', cascade = 'delete')

    def __repr__(self):
        return f"<Deck {self.id}|{self.deck_name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'deck_name': self.deck_name,
            'description': self.description,
            'user_id': self.user_id
        }


# Double sided cards will have a string that is their other sides 'search_name'
# When calling items late, there will be a condition along the lines of 'if double_sided_pointer == null, print normally, otherwise go into the tree of dealing with presenting double face and split cards.
class Card(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    card_name = db.Column(db.String(100), nullable = False)
    search_name = db.Column(db.String(100), nullable = False)
    oracle_text = db.Column(db.String, nullable = False)
    type_line = db.Column(db.String(100), nullable = False)
    power = db.Column(db.Integer, nullable = True)
    toughness = db.Column(db.Integer, nullable = True)
    mana_cost = db.Column(db.String(50), nullable = False)
    cmc = db.Column(db.Integer, nullable = False)
    color_identity = db.Column(db.String(5), nullable = False)
    card_img = db.Column(db.String, nullable = False)
    double_sided_pointer = db.Column(db.String(100), nullable = True)

    def __repr__(self):
        return f"<Card {self.id}|{self.card_name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'card_name': self.card_name,
            'search_name':self.search_name,
            'oracle_text': self.oracle_text,
            'type_line': self.type_line,
            'power': self.power,
            'toughness': self.toughness,
            'mana_cost': self.mana_cost,
            'cmc': self.cmc,
            'color_identity': self.color_identity,
            'mana_cost': self.mana_cost,
            'card_img': self.card_img,
            'double_sided_pointer' : self.double_sided_pointer
        }



class Keyword(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    keyword_name = db.Column(db.String(20), nullable = False)
    keyword_definition = db.Column(db.String, nullable = True)
    
    def __repr__(self):
        return f"<Keyword {self.id}|{self.keyword_name}>"

    def to_dict(self):
        return {
            'id': self.id,
            'keyword_name': self.keyword_name,
            'keyword_definition': self.keyword_definition,
        }



class Card_keyword(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    keyword_id = db.Column(db.Integer, db.ForeignKey('keyword.id'), nullable = False)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable = False)

    def __repr__(self):
        return f"<Card_Keyword {self.id}|{self.keyword_id}|{self.card_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'keyword_id': self.keyword_id,
            'card_id': self.card_id,
        }



class Commander_collection(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    commander_id = db.Column(db.Integer, db.ForeignKey('commander.id'), nullable = False)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable = False)

    def __repr__(self):
        return f"<Commander_Collection {self.id}|{self.commander_id}|{self.card_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'commander_id': self.commander_id,
            'card_id': self.card_id,
        }


class Deck_collection(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    is_commander = db.Column(db.Boolean, nullable = False, default = False)
    is_maindeck = db.Column(db.Boolean, nullable = False, default = True)
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id'), nullable = False)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable = False)
    

    def __repr__(self):
        return f"<Deck_collection {self.id}|{self.deck_id}|{self.card_id}>"

    def to_dict(self):
        return {
            'id': self.id,
            'is_commander':self.is_commander,
            'is_maindeck':self.is_maindeck,
            'deck_id': self.deck_id,
            'card_id': self.card_id,
        }


class Commander_gram(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    n_gram = db.Column(db.String(100), nullable = False)
    n_count = db.Column(db.Integer, nullable = False)
    commander_id = db.Column(db.Integer, db.ForeignKey('commander.id'), nullable = False)

    def __repr__(self):
        return f"<Commander_gram {self.id}|{self.commander_id}>"
    
    def to_dict(self):
        return {
            'id': self.id,
            'n_gram':self.n_gram,
            'n_count':self.n_count,
            'commander_id': self.commander_id
        }


class Cardgram(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    n_gram = db.Column(db.String(100), nullable = False)

    def __repr__(self):
        return f"<Cardgram {self.id}|{self.n_gram}>"

    def to_dict(self):
        return {
            'id':self.id,
            'n_gram':self.n_gram
        }

class Cardgram_collection(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    card_id = db.Column(db.Integer, db.ForeignKey('card.id'), nullable = False)
    cardgram_id = db.Column(db.Integer, db.ForeignKey('cardgram.id'), nullable = False)

    def __repr__(self):
        return f"<Cardgram_collection {self.id}|{self.card_id}|{self.cardgram_id}>"

    def to_dict(self):
        return {
            'id':self.id,
            'card_id':self.card_id,
            'cardgram_id':self.cardgram_id
        }

class Deck_search(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    search_term = db.Column(db.String(50), nullable = False)
    deck_id = db.Column(db.Integer, db.ForeignKey('deck.id'), nullable = False)

    def __repr__(self):
        return f"<Deck_search {self.id}|{self.search_term}|{self.deck_id}>"

    def to_dict(self):
        return {
            'id':self.id,
            'search_term':self.search_term,
            'deck_id':self.deck_id
        }