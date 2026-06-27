from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, TextAreaField, FloatField, SelectField, DateTimeField, BooleanField, IntegerField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional, NumberRange

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired()])
    remember = BooleanField('Remember Me')

class EventForm(FlaskForm):
    name = StringField('Event Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description', validators=[Optional()])
    event_date = DateTimeField('Event Date & Time', validators=[DataRequired()], format='%Y-%m-%dT%H:%M')
    venue = StringField('Venue', validators=[DataRequired(), Length(max=200)])
    max_teams = IntegerField('Maximum Teams', validators=[DataRequired(), NumberRange(min=1, max=100)], default=10)
    status = SelectField('Status', choices=[
        ('upcoming', 'Upcoming'),
        ('ongoing', 'Ongoing'),
        ('completed', 'Completed')
    ], validators=[DataRequired()])

class TeamForm(FlaskForm):
    name = StringField('Team Name', validators=[DataRequired(), Length(max=100)])
    institution = StringField('Institution/Organization', validators=[DataRequired(), Length(max=200)])
    leader_name = StringField('Team Leader Name', validators=[DataRequired(), Length(max=100)])
    leader_email = StringField('Team Leader Email', validators=[DataRequired(), Email(), Length(max=120)])
    leader_phone = StringField('Team Leader Phone', validators=[DataRequired(), Length(min=10, max=20)])
    event_id = SelectField('Select Event', validators=[DataRequired()], coerce=int)

class ScoreForm(FlaskForm):
    score = FloatField('Score', validators=[DataRequired(), NumberRange(min=0, max=100)])
    criteria = SelectField('Criteria', choices=[
        ('creativity', 'Creativity & Innovation'),
        ('execution', 'Execution & Presentation'),
        ('technical', 'Technical Excellence'),
        ('impact', 'Impact & Relevance'),
        ('overall', 'Overall Performance')
    ], validators=[DataRequired()])
    comments = TextAreaField('Comments', validators=[Optional(), Length(max=500)])

class AssignJudgeForm(FlaskForm):
    judge_id = SelectField('Select Judge', validators=[DataRequired()], coerce=int)
    event_id = SelectField('Select Event', validators=[DataRequired()], coerce=int)

class TeamRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=100)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])
    team_name = StringField('Team Name', validators=[DataRequired(), Length(max=100)])
    institution = StringField('Institution/Organization', validators=[DataRequired(), Length(max=200)])
    leader_name = StringField('Team Leader Name', validators=[DataRequired(), Length(max=100)])
    leader_phone = StringField('Team Leader Phone', validators=[DataRequired(), Length(min=10, max=20)])
    event_id = SelectField('Select Event', validators=[DataRequired()], coerce=int)


# Judge Registration Form
class JudgeRegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=100)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(), EqualTo('password', message='Passwords must match')])
    email = StringField('Email', validators=[DataRequired(), Email(), Length(max=120)])