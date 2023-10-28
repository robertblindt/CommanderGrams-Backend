from . import api
from app import db
from app.models import Card, User, Deck, Deck_collection, Deck_search, Commander, Commander_gram
from flask import request
from .auth import basic_auth
from .auth import basic_auth, token_auth
from app.processing import Processing

processor = Processing()


@api.route('/token')
@basic_auth.login_required
def get_token():
    auth_user = basic_auth.current_user()
    token = auth_user.get_token()
    return {
        'token':token,
        'token_expiration' : auth_user.token_expiration
    }


@api.route('/cards')
def see_cards():
    cards = db.session.execute(db.select(Card)).scalars().all()
    return [card.to_dict() for card in cards]


@api.route('/findcommander', methods = ["POST"])
def commander_search():
    # JSON Check
    if not request.is_json:
        return {'error': 'Your content-type must be application/json'}, 400
    data = request.json
    required_fields = ['commander']
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    if missing_fields:
        return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
    # I NEED TO CHECK THE DB IF I HAVE CG OF REQUESTED CARD.
    # IF I HAVE IT, GET CARDS LIST FROM DB.  OTHERWISE TELL THEM WE DONT HAVE IT.
    if processor._clean_search_input(data.get('commander'), 0) in db.session.execute(db.select(Commander.search_name)).scalars().all():
        return {'message':'GOT IT!'}
    return {'error':'Either the commander has not been scraped, or the name is misspelled!'}, 404

# I need to take the output of the scraper EC2 instance (a list of card names) and run them into the previous insert.
@api.route('/insertcommander', methods = ["POST"])
def commander_insert():
    # JSON Check
    if not request.is_json:
        return {'error': 'Your content-type must be application/json'}, 400
    data = request.json
    required_fields = ['commander', 'card_list']
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    if missing_fields:
        return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
    card_retrieval_list=data.get('card_list')
    if card_retrieval_list:
        processor.edhrec_list_db_check_and_retrieve(card_retrieval_list, data.get('commander'))
        # print(form.commander.data)
        processor.find_meaning(data.get('commander'))
        return {'message':'Commander has been added or updated!'}
    return {'error':'Either the commander has already been scraped, or the name is misspelled!'}


# @api.route('/user')
# def see_users():
#     users = db.session.execute(db.select(User)).scalars().all()
#     return [user.to_dict() for user in users]


@api.route('/users', methods=["POST"])
def create_user():
    # Check to see that the request body is JSON
    if not request.is_json:
        return {'error': 'Your content-type must be application/json'}, 400
    # Get the data from the request body
    data = request.json
    # Validate incoming data
    required_fields = ['firstName', 'lastName', 'username', 'email', 'password']
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    if missing_fields:
        return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
    

    first_name = data.get('firstName')
    last_name = data.get('lastName')
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    check_user = db.session.execute(db.select(User).where((User.username == username)|(User.email == email))).scalar()
    if check_user:
        return {'error':f"A user with that username and/or email already exists"}, 400

    # Create a new Post instance with the data
    new_user = User(first_name=first_name, last_name=last_name, username=username, email=email, password=password)
    # add to the database
    db.session.add(new_user)
    db.session.commit()

    return new_user.to_dict(), 201   


@api.route('/users/me')
@token_auth.login_required
def get_me():
    me = token_auth.current_user()    
    return me.to_dict()



@api.route('/deck', methods=["GET","POST"])
@token_auth.login_required
def create_deck():
    if request.method == "GET":
        my_decks = db.session.execute(db.select(Deck).where(Deck.user_id==token_auth.current_user().id)).scalars().all()
        return [deck.to_dict() for deck in my_decks]
    
    
    if request.method == "POST":
        if not request.is_json:
            return {'error': 'Your content-type must be application/json'}, 400
        # Get the data from the request body
        data = request.json
        # Validate incoming data
        required_fields = ['deckName', 'description']
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        if missing_fields:
            return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
        deck_name = data.get('deckName')
        description = data.get('description')
        # Create a new Deck instance with the data
        new_deck = Deck(deck_name = deck_name, description = description, user_id = token_auth.current_user().id)
        # add to the database
        db.session.add(new_deck)
        db.session.commit()
        return new_deck.to_dict(), 201   



@api.route('/deck/<deck_id>', methods=['POST','DELETE','GET','PUT'])
@token_auth.login_required
def modify_deck(deck_id):
    if request.method == "POST":
        if not request.is_json:
            return {'error': 'Your content-type must be application/json'}, 400
        # Get the data from the request body
        data = request.json
        # Validate incoming data
        required_fields = ['cardName']
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        if missing_fields:
            return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
        card = data.get('cardName')
        # need to retrieve card first?
        processor.add_card_deckbuilder(card, deck_id)
        return {"message":f"{card} added to deck {deck_id}"}
    
    if request.method == 'DELETE':
        if not request.is_json:
            return {'error': 'Your content-type must be application/json'}, 400
        # Get the data from the request body
        data = request.json
        # print(data)
        # Validate incoming data
        required_fields = ['cardName']
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        if missing_fields:
            return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
        card = data.get('cardName')
        # This will not tell you when you are trying to remove a card thats no there... Kinda doesnt matter and is favorable
        processor.remove_card_deckbuilder(card, deck_id)
        return {"message":f"{card} removed from deck {deck_id}"}
    
    if request.method == 'GET':
        my_deck = db.session.execute(
            db.select(Deck_collection, Card)
            .where(Deck_collection.deck_id==deck_id)
            .join(Card, Deck_collection.card_id == Card.id)).all()
        # print(my_deck[0][0].to_dict())
        # print(my_deck[0][1].to_dict())
        return_dict_list = []
        for card in my_deck:
            dc_dict = card[0].to_dict()
            card_dict = card[1].to_dict()
            return_dict = {
                "id":dc_dict.get('id'),
                "is_commander":dc_dict.get('is_commander'),
                "is_maindeck":dc_dict.get('is_maindeck'),
                "deck_id":dc_dict.get('deck_id'),
                "card_id":dc_dict.get('card_id'),
                "card_name":card_dict.get('card_name'),
                "search_name":card_dict.get('search_name'),
                "oracle_text":card_dict.get('oracle_text'),
                "type_line":card_dict.get('type_line'),
                "color_identity":card_dict.get('color_identity'),
                "card_img":card_dict.get('card_img'),
                "cmc":card_dict.get('cmc'),
                "double_sided_pointer":card_dict.get('double_sided_pointer')
            }
            return_dict_list.append(return_dict)
        # result = db.session.execute(my_deck)
        # print(result.scalars().all())
        return return_dict_list # [dc_connect.to_dict() for dc_connect in my_deck]
    
    if request.method == 'PUT':
        if not request.is_json:
            return {'error': 'Your content-type must be application/json'}, 400
        data = request.json
        required_fields = ['cardId', 'deckId']
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        if missing_fields:
            return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
        
        card = db.session.execute(db.select(Deck_collection).where((Deck_collection.card_id == data.get('cardId'))&(Deck_collection.deck_id == data.get('deckId')))).scalar()
        if card is None:
            return {'error':'You do not have that card in your deck.'},404
        deck_owner_id = db.session.execute(db.select(Deck.user_id).where(Deck.id == data.get('deckId'))).scalar()
        current_user = token_auth.current_user()
        # print(current_user.id, deck_owner_id)
        if deck_owner_id != current_user.id:
            return {'error':'You do not have authorization to edit this deck!'},403
        
        for field in data:
            if field in {'is_commander', 'is_maindeck'}:
                setattr(card,field,data[field])
        
        db.session.commit()
        return card.to_dict()
    
@api.route('/deck/<deck_id>/edit', methods=["GET","PUT","DELETE"])
@token_auth.login_required
def edit_deck_info(deck_id):
    if request.method == "GET":
        my_deck = db.session.execute(
            db.select(Deck).where((Deck.user_id==token_auth.current_user().id)&(Deck.id==deck_id))).scalar()
        return my_deck.to_dict()


    if request.method == "PUT":
        if not request.is_json:
            return {'error': 'Your content-type must be application/json'}, 400
        data = request.json        
        my_deck = db.session.execute(db.select(Deck).where((Deck.id == deck_id))).scalar()
        if my_deck is None:
            return {'error':'No deck found.'},404
        if my_deck.user_id != token_auth.current_user().id:
            return {'error':'You do not own that deck to edit.'},403
        for field in data:
            if field in {'deck_name', 'description'}:
                setattr(my_deck,field,data[field])
        db.session.commit()
        return my_deck.to_dict()
    
    
    if request.method == "DELETE":
        my_deck = db.session.execute(db.select(Deck).where((Deck.id == deck_id) & (Deck.user_id == token_auth.current_user().id))).scalar()
        db.session.delete(my_deck)
        db.session.commit()
        return {'message':f"Deck {deck_id} deleted!"}
    

@api.route('/search', methods=["POST"])
@token_auth.login_required
def search_for_card():
    if not request.is_json:
        return {'error': 'Your content-type must be application/json'}, 400
    # Get the data from the request body
    data = request.json
    # Validate incoming data
    required_fields = ['cardName']
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    if missing_fields:
        return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
    return_dict_lst = []
    cards = processor.search_cards(data.get('cardName'))
    # print(cards)
    if cards == None:
        return {"error": "Could not find card on Scryfall."}, 404
    for item in cards:
        card_name = item.get('name')
        oracle_text = item.get('oracle_text')
        type_line = item.get('type_line')
        card_img = item.get('image_uris',{1:2}).get('border_crop','https://lh3.googleusercontent.com/d/1CQbMtyQLYltrEOjWLfgxqPIFzntvxNJP=w400-h400?authuser=0')
        card_dict = {
            "card_name":card_name,
            "oracle_text":oracle_text,
            "type_line":type_line,
            "card_img":card_img
        }
        return_dict_lst.append(card_dict)


    return return_dict_lst, 200 

@api.route('/search/commander', methods=["POST"])
def show_commander():
    if not request.is_json:
        return {'error': 'Your content-type must be application/json'}, 400
    # Get the data from the request body
    data = request.json
    # Validate incoming data
    required_fields = ['cardName']
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    if missing_fields:
        return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
    return_dict_lst = []
    cards = processor.retrieve_commandergrams(data.get('cardName'))
    # print(cards)
    if cards == None:
        return {"error": "Could not find card on Scryfall."}, 404
    return cards, 200 


@api.route('/deck/<deck_id>/searchterm', methods=["GET","POST"])
@token_auth.login_required
def add_deck_search_terms(deck_id):
    if request.method == "GET":
        search_terms = db.session.execute(
            db.select(Deck_search).where(Deck_search.deck_id == deck_id)).scalars().all()
        return_dict_lst = processor.deck_count(search_terms, deck_id)
        # print(return_dict_lst)
        return return_dict_lst

    if request.method == "POST":
        if not request.is_json:
            return {'error': 'Your content-type must be application/json'}, 400
        # Get the data from the request body
        data = request.json
        # Validate incoming data
        required_fields = ['search_term', 'deck_id']
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)
        if missing_fields:
            return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
        search_term = data.get('search_term')
        deck_id = data.get('deck_id')
        new_search_term = Deck_search(search_term = search_term, deck_id = deck_id)
        db.session.add(new_search_term)
        db.session.commit()
        return new_search_term.to_dict(), 201

    

@api.route('/deck/<search_term_id>/searchterm', methods=["DELETE"])
@token_auth.login_required
def delete_search_term(search_term_id):
    if request.method == "DELETE":
        my_search_term = db.session.execute(db.select(Deck_search).where((Deck_search.id == search_term_id))).scalar()
        db.session.delete(my_search_term)
        db.session.commit()
        return {'message':f"Search Term {search_term_id} deleted!"}
    

@api.route('/deck/<deck_id>/dump', methods=["POST"])
@token_auth.login_required
def deck_dump(deck_id):
    if not request.is_json:
        return {'error': 'Your content-type must be application/json'}, 400
    # Get the data from the request body
    data = request.json
    # Validate incoming data
    required_fields = ['cards']
    missing_fields = []
    for field in required_fields:
        if field not in data:
            missing_fields.append(field)
    if missing_fields:
        return {'error': f"{', '.join(missing_fields)} must be in the request body"}, 400
    search_term = data.get('cards')
    print(search_term.split('\n'))
    cards_for_insert =  search_term.split('\n')
    # Make sure its formatted correctly!
    if not cards_for_insert[0].split('x ')[0].isnumeric():
        return {"error":"Formatting Error. Please check that you removed deck identifiers like 'Mainboard'"}, 400

    previous_cards = db.session.execute(db.select(Deck_collection).where((Deck_collection.deck_id == deck_id))).scalars().all()
    print(previous_cards)
    for card in previous_cards:
        db.session.delete(card)
        db.session.commit()
    for card in cards_for_insert:
        # This should catch and pass by sideboard being in deck.  Wont let you know though...
        if 'x ' in card:
            card_split = card.lower().split('x ')
            # print(card_split)
            clean_name = processor._clean_search_input('x '.join(card_split[1:]),0)
            for i in range(int(card_split[0])):
                processor.scryfall_check_and_retrieve(clean_name,db)
                processor.add_card_deckbuilder(clean_name, deck_id)
    return {"message":"Deck transfer complete"}


@api.route('/commanders', methods=["GET"])
def get_commanders():
    # commanders = db.session.execute(
    #     db.select(Commander.commander_name)).scalars().all()
    commanders = db.session.execute(
        db.select(Commander_gram.commander_id).distinct()
        ).scalars().all()
    commanders = db.session.execute(
        db.select(Commander.commander_name).where(Commander.id.in_(db.session.execute(
        db.select(Commander_gram.commander_id).distinct()
        ).scalars().all()))).scalars().all()
    # print(commanders)
    return commanders