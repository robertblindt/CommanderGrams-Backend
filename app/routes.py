from app import app, db
from flask import render_template, redirect, url_for, flash
from app.forms import CommanderSearch, SignUpForm, LoginForm, CreateDeckForm, SearchForCard, AddCard, RemoveCard
from app.models import User, Commander, Deck, Card, Keyword, Card_keyword, Commander_collection, Deck_collection
from app.processing import Processing
from flask_login import login_user, logout_user, login_required, current_user

processor = Processing()

@app.route('/', methods = ["GET","POST","PUT"])
def index():
    form = CommanderSearch()
    if form.validate_on_submit():
        # print(form.commander.data)
        card_retrieval_list = processor.parseEDHrec_for_card_names(form.commander.data)
        if card_retrieval_list:
            processor.edhrec_list_db_check_and_retrieve(card_retrieval_list, form.commander.data)
            print(form.commander.data)
            processor.find_meaning(form.commander.data)

            print("OOO you searched for a commander! Nicely done!")
            return redirect(url_for('index'))
    
    # return 'Hello!' 
    return render_template('index.html', form = form)

@app.route('/signup', methods = ["GET","POST"])
def signup():
    form = SignUpForm()
    if form.validate_on_submit():
        # get the data from the form
        first_name = form.first_name.data
        last_name = form.last_name.data
        username = form.username.data
        email = form.email.data
        password = form.password.data
        # print(first_name,last_name,username,email,password)

        check_user = db.session.execute(db.select(User).where((User.username == username)|(User.email==email))).scalar()
        if check_user:
            flash(f'A user of that username and or email already exists!', "danger")
            # Why does this not keep the form data?
            return redirect(url_for('signup'))

        user = User(first_name = first_name, last_name = last_name, email = email, username = username, password = password)
        db.session.add(user)
        db.session.commit()
        flash(f'{user.username} has been created!', "success")

        # Login the user
        # login_user(user)
        
        return redirect(url_for('index'))
    
    elif form.is_submitted():
        flash("Your passwords do not match", "danger")
        return redirect(url_for('signup'))
    
    return render_template('signup.html', form = form)

@app.route('/login', methods=["GET","POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data
        password = form.password.data
        # Query the user table for a user with that username
        user = db.session.execute(db.select(User).where(User.username==username)).scalar()

        # If we have the user AND if the password is correct
        if user is not None and user.check_password(password):
            flash(f'{user.username} has been logged in!', "success")
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash(f'Invalid username and/or password!', "danger")

    return render_template('login.html',form = form)


@app.route('/createdeck', methods = ["GET","POST"])
@login_required
def createdeck():
    my_decks = db.session.execute(db.select(Deck).where(Deck.user_id==current_user.id)).scalars().all()
    print(my_decks)

    form = CreateDeckForm()
    if form.validate_on_submit():
        deck_name = form.deck_name.data
        description = form.description.data
        new_deck = Deck(deck_name = deck_name, description = description, user_id = current_user.id)
        db.session.add(new_deck)
        db.session.commit()
        return redirect(url_for('index'))

    return render_template('createdeck.html', form = form, my_decks = my_decks)
    

@app.route('/deck/<int:deck_id>', methods = ["GET","POST","DELETE"])
def deck_builder(deck_id):
    deck = db.session.execute(db.select(Deck_collection).where(Deck_collection.deck_id == deck_id)).scalars().all()
    deck_cards = [db.session.execute(db.select(Card).where(Card.id == card.card_id)).scalar() for card in deck]
    form = SearchForCard()
    form2 = AddCard()
    form3 = RemoveCard()
    maybe_cards = ''
    if form.validate_on_submit():
        card_requested = form.search_card.data
        maybe_cards = processor.search_cards(card_requested)
        if maybe_cards == None:
            maybe_cards = []
        else:
            print(processor._clean_search_input(maybe_cards[0]['name'],0))
            processor.add_card_deckbuilder(maybe_cards[0], deck_id)
            # processor.remove_card_deckbuilder(maybe_cards[0], deck_id)

    # THESE BUTTONS DONT WORK!!!! I AM GOING TO JUST AUTOMATICALLY ADD THE FIRST ONE AND THEN REMOVE THE FIRST ONE FOR A BIT.
    if form2.validate_on_submit():
        print('Add triggered')
    
    if form3.validate_on_submit():
        print('remove triggered')
    
    print(deck_cards)
        
    return render_template('deckbuilder.html', form = form, form2=form2, form3=form3, deck = deck_cards, maybe_cards = maybe_cards)







# def create_user(fn,ln,un,pw,em):
#     u1 = User(first_name = fn, last_name = ln, username = un, password = pw, email = em)
#     db.session.add(u1) 
#     db.session.commit()