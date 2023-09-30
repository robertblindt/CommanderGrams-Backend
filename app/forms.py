from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, EmailField, SubmitField, TextAreaField
from wtforms.validators import InputRequired, EqualTo


class CommanderSearch(FlaskForm):
    commander = StringField('Commander', validators = [InputRequired()])
    submit = SubmitField('Search')


class SignUpForm(FlaskForm):
    first_name = StringField('First Name', validators = [InputRequired()])
    last_name = StringField('Last Name', validators = [InputRequired()])
    username = StringField('Username', validators = [InputRequired()])
    email = EmailField('Email', validators = [InputRequired()])
    password = PasswordField('Password', validators = [InputRequired()])
    confirm_pass = PasswordField('Confirm Password', validators = [InputRequired(), EqualTo('password')])
    submit = SubmitField('Sign Up')


class LoginForm(FlaskForm):
    username = StringField('Username', validators = [InputRequired()])
    password = PasswordField('Password', validators = [InputRequired()])
    submit = SubmitField('Login')


class CreateDeckForm(FlaskForm):
    deck_name = StringField('Deck Name', validators=[InputRequired()])
    description = TextAreaField('Description')
    submit = SubmitField('Create Deck')


class SearchForCard(FlaskForm):
    search_card = StringField('Search for Cards', validators = [InputRequired()])
    submit = SubmitField('Search')


class AddCard(FlaskForm):
    add = SubmitField('Add')

class RemoveCard(FlaskForm):
    remove = SubmitField('Remove')
