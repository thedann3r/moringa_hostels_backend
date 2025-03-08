from flask import Flask, request, jsonify
from flask_restful import Resource, Api
from models import User, Accommodations, Booking, db, Rooms, Reviews
from datetime import datetime, timedelta
from werkzeug.security import check_password_hash
from flask_bcrypt import Bcrypt
from flask_jwt_extended import jwt_required, get_jwt_identity

app = Flask(__name__)
bcrypt = Bcrypt(app)

class Users(Resource):
    def get(self, id):
        user = User.query.get(id)
        if not user:
            return {'message': 'User not found'}, 404
        return {'id': user.id, 'name': user.name, 'email': user.email}

    @jwt_required()
    def patch(self, id):
        current_user = get_jwt_identity()

        if int(current_user['id']) != int(id):
            return {'error': 'You can only update your own profile'}, 403

        user = User.query.get(id)
        if not user:
            return {'error': 'User not found'}, 404

        data = request.get_json()
        new_name = data.get('name')
        new_email = data.get('email')
        new_password = data.get('new_password')

        if new_name:
            user.name = new_name
        if new_email:
            user.email = new_email

        if new_password and new_password.strip():
            current_password = data.get('current_password')
            if not current_password:
                return {'error': 'Current password is required to change password'}, 400
            if not check_password_hash(user.password, current_password):
                return {'error': 'Incorrect current password'}, 401
            user.password = bcrypt.generate_password_hash(new_password).decode('utf-8')

        db.session.commit()
        return {'message': 'Profile updated successfully'}, 200
    
    @jwt_required
    def delete(self, id):
        current_user = get_jwt_identity() 

        if int(current_user['id']) != int(id):
            return {'error': 'You can only delete your own account'}, 403
        
        user = User.query.get(id)
        if not user:
            return {'message': 'User not found'}, 404
        
        db.session.delete(user)
        db.session.commit()
        return {'message': 'User deleted successfully'}, 200

class AccommodationList(Resource):
    def get(self):
        accommodations = Accommodations.query.all()
        if not accommodations:
            return {"error": "Accommodation not found"}, 404
        return [accommo.to_dict() for accommo in accommodations]
    
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        if current_user['role'] != 'admin':
            return {'error': 'The user is forbidden from adding new accommodations!'}, 403

        data = request.get_json()
        required_fields = {'name', 'image', 'description', 'latitude', 'longitude'}
        if not data or not all(key in data for key in required_fields):
            return {'error': 'Missing required fields!'}, 422
        
        new_accommodation = Accommodations(
            name=data['name'],
            image=data['image'], 
            description=data['description'],
            latitude=data['latitude'],
            longitude=data['longitude']
        )
        db.session.add(new_accommodation)
        db.session.commit()
        return new_accommodation.to_dict(), 201


class Accommodation(Resource):
    def get(self, id):
        accommodation = Accommodations.query.get(id)
        if not accommodation:
            return {"message": "Accommodation not found"}, 404
        
        return {
            "id": accommodation.id,
            "name": accommodation.name,
            "description": accommodation.description,
            "latitude": accommodation.latitude,
            "longitude": accommodation.longitude
        }

    @jwt_required()
    def patch(self, id):
        current_user = get_jwt_identity()
        if current_user['role'] != 'admin':
            return {'error': 'The user is forbidden from editing the accommodations!'}, 403
        
        data = request.get_json()
        accommodation = Accommodations.query.get(id)
        
        if not accommodation:
            return {'message': 'Accommodation not found'}, 404
        
        if 'name' in data:
            accommodation.name = data['name']
        if 'description' in data:
            accommodation.description = data['description']
        if 'image' in data:
            accommodation.image = data['image']
        if 'latitude' in data:
            accommodation.latitude = data['latitude']
        if 'longitude' in data:
            accommodation.longitude = data['longitude']

        db.session.commit()
        return accommodation.to_dict(), 200
    
    def put(self, id):
        accommodation = Accommodations.query.get(id)
        if not accommodation:
            return {'message': 'Accommodation not found'}, 404

        data = request.get_json()
        if 'name' in data:
            accommodation.name = data['name']
        if 'description' in data:
            accommodation.description = data['description']
        if 'image' in data:
            accommodation.image = data['image']
        if 'latitude' in data:
            accommodation.latitude = data['latitude']
        if 'longitude' in data:
            accommodation.longitude = data['longitude']

        db.session.commit()
        return accommodation.to_dict(), 200

    @jwt_required()
    def delete(self, id):
        current_user = get_jwt_identity()
        if current_user['role'] != 'admin':
            return {'error' : 'The user is forbidden from deleting the accommodations!'}, 403
    
        accommodation = Accommodations.query.get(id)
        if not accommodation:
            return {'message': 'Accommodation not found!'}, 404
        db.session.delete(accommodation)
        db.session.commit()
        return {'message': 'Accommodation and its associated rooms have been deleted successfully!'}, 200

    
# Rooms
class Room(Resource):
    def get(self):
        accommodation_id = request.args.get('accommodation_id')  

        if accommodation_id:
            rooms = Rooms.query.filter_by(accommodation_id=accommodation_id).all()
        else:
            rooms = Rooms.query.all() 

        if not rooms:
            return {"error": "Rooms not found"}, 404

        return [room.to_dict() for room in rooms], 200 
    
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        if current_user['role'] != 'admin':
            return {'error' : 'The user is forbidden from adding new rooms!'}, 403

        data = request.get_json()
        if not data or not all (key in data for key in ('room_no','room_type','price', 'accommodation_id', 'availability', 'image', 'description')):
            return {'error': 'Missing required fields!'}, 422
        
        room_no = data['room_no']
        min = 1
        max = 100
        if room_no < min or room_no > max:
            return {'error' : f'Hostel rooms must be between {min} and {max} respectively!'},400
        
        price = data['price']
        min = 5000
        max = 30000
        if price < min or price > max:
            return {'error' : f'Room price must be between {min} and {max} price!'},400
        availability = data['availability']  
        if not isinstance(availability, bool):
           return {'error': 'Availability must be a boolean value!'}, 422


        new_room = Rooms(
            room_no = room_no,
            price = price,
            room_type = data['room_type'],
            accommodation_id=data.get('accommodation_id'),
            availability=availability,
            image=data['image'],
            description=data['description']
        )
        db.session.add(new_room)
        db.session.commit()
        return new_room.to_dict(), 201

class RoomList(Resource):
    @jwt_required()
    def get(self, id):
        accommodation = Rooms.query.get(id)
        return {
            "id": accommodation.id,
            "room_no": accommodation.room_no,
            "room_type": accommodation.room_type,
            "price": accommodation.price,
            "accommodation_id": accommodation.accommodation_id,
            "image": accommodation.image,
            "availability": accommodation.availability,
            "description": accommodation.description
        }
    
    @jwt_required()
    def patch(self, id):
        current_user = get_jwt_identity()
        if current_user['role'] != 'admin':
            return {'error' : 'The user is forbidden from editing the accommodations!'}, 403
        
        data = request.get_json()
        accommodation = Rooms.query.get(id)
        
        if not accommodation:
            return {'message': 'Accommodation not found'}, 404
        
        if 'room_no' in data:
            room = data ['room_no']
            min = 1
            max = 100
            if room < min or room > max:
                return {'error' : f'Hostel rooms must be between {min} and {max} respectively!'},400
            accommodation.room_no = room

        if 'price' in data:
            price = data['price']
            min = 5000
            max = 30000
            if price < min or price > max:
                return {'error' : f'Room price must be between {min} and {max} price!'},400
            accommodation.price = price

        if 'accommodation_id' in data:
            accommodation.accommodation_id = data ['accommodation_id']
        if 'room_type' in data:
            accommodation.room_type = data ['room_type']
        if 'availability' in data:
            availability = data['availability']
        if not isinstance(availability, bool):
           return {'error': 'Availability must be a boolean value!'}, 422
        accommodation.availability = availability
        if 'image' in data:
            accommodation.image = data ['image']
        if 'description' in data:
            accommodation.description = data ['description']
        db.session.commit()
        return accommodation.to_dict(), 200
    
    @jwt_required()
    def delete(self, id):
        current_user = get_jwt_identity()
        if current_user['role'] != 'admin':
            return {'error' : 'The user is forbidden from deleting the rooms!'}, 403
        
        accommodation = Rooms.query.get(id)
        if not accommodation:
            return {'message': 'room not found!'}, 404
        db.session.delete(accommodation)
        db.session.commit()
        return {'message': 'room deleted successfully!'}
    
class RoomListResource(Resource):
    def get(self):
        accommodation_id = request.args.get('accommodation_id')
        query = db.session.query(Rooms)

        if accommodation_id:
            query = query.filter(Rooms.accommodation_id == int(accommodation_id))  

        rooms = [room.to_dict() for room in query.all()]
        return rooms, 200  
    
class Review(Resource):
    def get (self):
        reviews = Reviews.query.all()
        if not reviews:
            return {"error": "reviews not found"}, 404
        return [accommo.to_dict() for accommo in reviews]
    
    @jwt_required()
    def post(self):
        current_user = get_jwt_identity()
        print("JWT Identity Debug:", current_user)

        if current_user["role"] != "user":
            return {"error": "The user is forbidden from adding new reviews!"}, 403

        data = request.get_json()

        if not data or not all(key in data for key in ("rating", "content")):
            return {"error": "Missing required fields!"}, 422

        try:
            rating = int(data.get("rating"))
            rating = max(1, min(5, rating))
        except ValueError:
            return {"error": "Rating must be a valid number!"}, 400

        new_review = Reviews(
            user_id=current_user["id"],  
            rating=rating,
            content=data["content"],
        )

        db.session.add(new_review)
        db.session.commit()

        return new_review.to_dict(), 201

class MyReview(Resource):
    @jwt_required()
    def get(self):
        current_user = get_jwt_identity()
        user_reviews = Reviews.query.filter_by(user_id=current_user['id']).all()

        if not user_reviews:
            return {"message": "You have no reviews yet."}, 404

        return [review.to_dict() for review in user_reviews], 200
    
    
class ReviewList(Resource): 
    
    @jwt_required()
    def get(self, id):
        review = Reviews.query.get(id)
        return {
            "id": review.id,
            "rating": review.rating,
            "user_id": review.user_id,
            "content": review.content
        }
    
    @jwt_required()
    def delete(self, id):
        current_user = get_jwt_identity()

        reviews = Reviews.query.get(id)

        if current_user['role'] != 'admin' and reviews.user_id != current_user['id']:
            return {'error': 'You are not authorized to delete this review!'}, 403
        
        if not reviews:
            return {'message': 'reviews not found!'}, 404
        
        db.session.delete(reviews)
        db.session.commit()
        return {'message': 'reviews deleted successfully!'}

#Bookings
class BookingsList(Resource):
    @jwt_required()
    def get(self):
        current = get_jwt_identity()
        if current['role'] != 'admin':
            return {'error': 'The user is not authorized!'}, 403
        
        bookings = Booking.query.all()
        if not bookings:
            return {"error": "No bookings found!"}, 404

        return [booking.to_dict() for booking in bookings]
    
    @jwt_required()
    def post(self):
        current = get_jwt_identity()
        if current['role'] != 'user':
            return {'error' : 'the user is not authorized!'}, 403
        
        data = request.get_json()

        if not data or not all (key in data for key in ('accommodation_id', 'room_id', 'start_date', 'end_date')):
            return {'error': 'Missing required fields!'}, 422
       
        try:
            start_date = datetime.strptime(data['start_date'], "%Y-%m-%d %H:%M") 
            end_date = datetime.strptime(data['end_date'], "%Y-%m-%d %H:%M")
        except ValueError:
            return {'error': 'Invalid date format. Use YYYY-MM-DD HH:MM'}, 400
        
        min_duration = timedelta(days=30)
        if(end_date - start_date) < min_duration:
            return{'error' : 'A booking must be atleast 1 month(30 days)!'}, 400
        
        user_id=current['id']
        accommodation_id=data['accommodation_id']
        room_id=data['room_id']

        room = Rooms.query.get(room_id)
        if not room :
            return {"error": "The room does not exist!"}, 404
        if room.accommodation_id != accommodation_id:
            return {"error": "The room does not belong to the accommodation!"}, 404

        existing_booking = Booking.query.filter(
            Booking.room_id == room.id, 
            Booking.end_date > start_date,
            Booking.start_date < end_date
        ).first()

        if existing_booking:
            return {"error" : "Room is already booked for selected dates!"},400
        
        booking = Booking(
            user_id = user_id,
            accommodation_id = accommodation_id,
            room_id = room.id,
            start_date = start_date,
            end_date = end_date,
            status="confirmed"
        )

        db.session.add(booking)
        room.availability = "booked!"
        db.session.commit()
        return booking.to_dict(),201
    
class CancelBooking(Resource):
    @jwt_required()
    def patch(self, id):
        current = get_jwt_identity()

        booking = Booking.query.get(id)
        if not booking:
            return {'message': 'Booking not found!'}, 404

        if current['role'] != 'admin' and booking.user_id != current['id']:
            return {'error': 'Unauthorized to cancel this booking!'}, 403

        if booking.status == "canceled":
            return {'message': 'Booking is already canceled!'}, 400

        booking.status = "canceled"
        
        if booking.room:
            booking.room.availability = "available!"

        db.session.commit()

        return {
            'message': 'Booking canceled successfully!',
            'booking': {
                'id': booking.id,
                'status': booking.status,
                'room_availability': booking.room.availability
            }
        }, 200

class Bookings(Resource):
    @jwt_required()
    def get(self):
        current = get_jwt_identity()
        user_id = current.get('id')
        user_role = current.get('role')

        if not user_id:
            return {'error': 'User not found!'}, 403

        # Fetch bookings based on user role
        if user_role == 'admin':
            bookings = Booking.query.all()
        else:
            bookings = Booking.query.filter_by(user_id=user_id).all()

        if not bookings:
            return {'message': 'No bookings found!'}, 404

        return [{
            'id': book.id,
            'user_id': book.user_id,
            'accommodation_id': book.accommodation_id,
            'room_id': book.room_id,
            'start_date': book.start_date.isoformat() if book.start_date else None,
            'end_date': book.end_date.isoformat() if book.end_date else None,
            'status': book.status,
            'room_type': book.room.room_type if book.room else None,
            'room_image': book.room.image if book.room else None,
            'room_description': book.room.description if book.room else None,
            'room_price': book.room.price if book.room else None,
            'accommodation_id': book.room.accommodation_id if book.room else None
        } for book in bookings], 200


class RoomBookings(Resource):
    def get(self, room_no):
        bookings = Booking.query.filter_by(room_id=room_no).all()
        if not bookings:
            return {"message": "No bookings found for this room."}, 404

        return [{
            "start_date": booking.start_date.strftime("%Y-%m-%d %H:%M"),
            "end_date": booking.end_date.strftime("%Y-%m-%d %H:%M")
        } for booking in bookings]