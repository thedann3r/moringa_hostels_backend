from flask import Flask, request, jsonify
from flask_migrate import Migrate
from flask_cors import CORS
import os
import re
import requests
from dotenv import load_dotenv
from flask_bcrypt import Bcrypt
from flask_restful import Resource, Api
from flask_jwt_extended import JWTManager, create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from resources.crude import Accommodation,AccommodationList,Users,Bookings,BookingsList, Room, RoomList, Review, ReviewList, MyReview, RoomBookings, RoomListResource, CancelBooking
from models import db, User, Accommodations,Rooms

import json
import base64
import datetime

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')
app.config['JWT_SECRET_KEY'] = os.getenv('SECRET_KEY', 'default_secret_key')

EMAIL_VALIDATION_API_URL = os.getenv('EMAIL_VALIDATION_API_URL')
EMAIL_VALIDATION_API_KEY = os.getenv('EMAIL_VALIDATION_API_KEY')

db.init_app(app)
migrate = Migrate(app,db)

CORS(app, supports_credentials=True)

api = Api(app)
bcrypt = Bcrypt(app)
jwt = JWTManager(app)

consumer_key = os.getenv('CONSUMER_KEY')
consumer_secret = os.getenv('CONSUMER_SECRET')
shortcode = os.getenv('SHORTCODE')
passkey = os.getenv('PASSKEY')
callback_url = "https://0e87-197-248-19-111.ngrok-free.app/mpesa/callback"

@app.route('/mpesa/pay', methods = ['POST'])
def mpesa_pay():
    phone_number = request.json.get('phone_number')
    amount = request.json.get('amount')

    access_token = get_access_token()
    if not access_token:
        return jsonify({'error' : 'Failed to get mpesa access token!'}), 500
    
    headers = {
        'Authorization' : f'Bearer {access_token}',
        'Content-Type' : 'application/json'
    }

    timestamp = get_timestamp()
    print(f"Generated Timestamp: {timestamp}")
    password = generate_password(shortcode, passkey, timestamp)

    payload = {
        "BusinessShortCode" : shortcode,
        "Password" : password,
        "Timestamp" : timestamp,
        "TransactionType" : "CustomerPayBillOnline",
        "Amount" : amount,
        "PartyA" : phone_number,
        "PartyB" : shortcode,
        "PhoneNumber" : phone_number,
        "CallBackURL" : callback_url,
        "AccountReference" : "12345678",
        "TransactionDesc" : "Payment for abc"
    }

    stk_push_url = "https://sandbox.safaricom.co.ke/mpesa/stkpush/v1/processrequest"
    response = requests.post(stk_push_url, json=payload, headers=headers)

    if response.status_code == 200:
        return jsonify({'message' : 'STK push initiated successfully', "data": response.json()}), 200
    else:
        return jsonify({'error' : 'Failed to initiate STK push', 'data': response.json()}), 500
    
@app.route('/mpesa/callback', methods = ['POST'])
def mpesa_callback():
    data = request.get_json()

    with open('mpesa_callback.log', 'a') as log_file:
        log_file.write(json.dumps(data, indent=4) + '\n\n')

    try:
        result_code = data['Body']['stkCallback']['ResultCode']
        result_desc = data['Body']['stkCallback']['ResultDesc']

        if result_code == 0:
            callback_metadata = data['Body']['stkCallback']['CallbackMetadata']['Item']
            amount = next(item['Value'] for item in callback_metadata if item['Name'] == 'Amount')
            mpesa_receipt_number = next(item['Value'] for item in callback_metadata if item['Name'] == 'MpesaReceiptNumber')
            phone_number = next(item['Value'] for item in callback_metadata if item['Name'] == 'PhoneNumber')

            payment_status = {
                'status' : 'success',
                'amount' : amount,
                'receipt' : mpesa_receipt_number,
                'phone' : phone_number,
                'message' : 'Payment received successfully!'
            }

        else:
            payment_status = {
                'status' : 'Failed',
                'message' : result_desc
            }
        return jsonify ({'message' : 'Callback received!'}), 200

    except KeyError:
        return jsonify ({'error' : 'invalid callback data'}), 400


    
def get_access_token():
    url = 'https://sandbox.safaricom.co.ke/oauth/v1/generate?grant_type=client_credentials'
    response = requests.get(url, auth=(consumer_key, consumer_secret))
    return response.json().get('access_token') if response.status_code == 200 else None

def generate_password(shortcode, passkey, timestamp):
    data_to_encode = f'{shortcode}{passkey}{timestamp}'
    return base64.b64encode(data_to_encode.encode()).decode('utf-8')

def get_timestamp():
    return datetime.datetime.now().strftime('%Y%m%d%H%M%S')

@app.route('/')
def index():
    return 'Welcome to the home page!'

def is_real_email(email):
    response = requests.get(f"{EMAIL_VALIDATION_API_URL}?email={email}&api_key={EMAIL_VALIDATION_API_KEY}")
    data = response.json()
    
    if response.status_code == 200 and data.get('data', {}).get('result') == 'deliverable':
        return True
    return False

def is_valid_email(email):
    return re.match(r"[^@]+@[^@]+\.[^@]+", email)

def is_strong_password(password):
    return bool(re.match(r"^(?=.*[A-Za-z])(?=.*\d)[A-Za-z\d@$!%*?&]{8,}$", password))


class Signup(Resource):
    def post(self):
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        confirm_password = data.get('confirm_password')  # Get confirm password
        role = data.get('role', 'user')

        if not is_valid_email(email):
            return {'error': 'Invalid email format, please provide a valid email address.'}, 400

        if User.query.filter_by(email=email).first():
            return {'error': 'Email already exists!'}, 400

        if not is_strong_password(password):
            return {'error': 'Password must be at least 8 characters long and contain both letters and numbers.'}, 400

        # ✅ Check if password matches confirm_password
        if password != confirm_password:
            return {'error': 'Passwords do not match!'}, 400

        # Hash and store only the password
        hash = bcrypt.generate_password_hash(password).decode('utf-8')
        new_user = User(name=name, email=email, password=hash, role=role)
        db.session.add(new_user)
        db.session.commit()

        create_token = create_access_token(identity={'id': new_user.id, 'name': new_user.name, 'email': new_user.email, 'role': new_user.role})

        return {
            'message': 'User created successfully!',
            'create_token': create_token,
            'user': {
                'id': new_user.id,
                'name': new_user.name,
                'email': new_user.email,
                'role': new_user.role
            }
        }, 201

    
class Login(Resource):
    def post(self):
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        role = data.get('role', 'user')

        user = User.query.filter_by(name=name, email=email).first()
        
        if user and bcrypt.check_password_hash(user.password, password):
            create_token = create_access_token(identity={'id':user.id, 'name':user.name, 'email':user.email, 'role':user.role})
            refresh_token = create_refresh_token(identity={'id':user.id, 'name':user.name, 'email':user.email, 'role':user.role})
            return {
                'create_token': create_token,
                'refresh_token': refresh_token,
                'role': user.role,
                'user': {
                    'id': user.id,
                    'name': user.name,
                    'email': user.email,
                    'role': user.role
                }
            }

        return {'error' : 'Incorrect name, email or password, please try again!'}, 401

class DeleteAcc(Resource):
    @jwt_required()
    def delete(self):
        current = get_jwt_identity()
        user_id = current.get('id')
        role = current.get('role')

        data = request.get_json()
        target_user_id = data.get('user_id') if data else user_id

        if role != "admin" and target_user_id != user_id:
            return {'error': 'Unauthorized action!'}, 403

        delete_user = User.query.get(target_user_id)
        if not delete_user:
            return {'error': 'The user does not exist!'}, 404

        db.session.delete(delete_user)
        db.session.commit()
        return {'message': 'The user was deleted successfully!'}, 200

    
class Refresh(Resource):
    @jwt_required(refresh = True)
    def post(self):
        current_user = get_jwt_identity()
        new_access_token = create_refresh_token(identity = current_user)
        return{'access_token':new_access_token}, 201
    
class Accommodate(Resource):
    @jwt_required()
    def get(self):
        accommodations = Accommodations.query.all()
        return[{'id':acom.id, 'name':acom.name,'user_id':acom.user_id, 'price':acom.price, 'image':acom.image,'description':acom.description, 'availability':acom.availability} for acom in accommodations]

class Use(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()

        if current_user['role'] != 'admin':
            return {'error': 'Access forbidden!'}, 403

        users = User.query.all()

        return [{'id': user.id, 'name': user.name, 'email': user.email, 'role': user.role} for user in users], 200


api.add_resource(Signup, '/signup')
api.add_resource(Login, '/login')
api.add_resource(Refresh, '/refresh')
api.add_resource(DeleteAcc, '/delete')
api.add_resource(Accommodate, '/accommodate')
api.add_resource(Use, '/users')

api.add_resource(AccommodationList, '/accommodations')
api.add_resource(Accommodation, '/accommodations/<int:id>')

api.add_resource(Room, '/rooms')
api.add_resource(RoomList, '/rooms/<int:id>')
api.add_resource(RoomListResource, '/rooms')

api.add_resource(Users, '/users/<int:id>')

api.add_resource(Review, '/reviews')
api.add_resource(ReviewList, '/reviews/<int:id>')
api.add_resource(MyReview, '/my-reviews')

api.add_resource(BookingsList, '/bookings', '/bookings/<int:id>' )
api.add_resource(Bookings, '/Userbookings')
api.add_resource(CancelBooking, "/bookings/<int:id>/cancel")

# api.add_resource(RoomBookings, "/bookings/room/<int:room_no>")

api.add_resource(RoomBookings, "/rooms/<int:room_id>/booked-dates")

if __name__ == '__main__':
    app.run(debug=True)