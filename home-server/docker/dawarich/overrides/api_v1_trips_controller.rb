# frozen_string_literal: true

class Api::V1::TripsController < ApiController
  before_action :authenticate_active_api_user!, only: %i[create update destroy]

  def index
    trips = current_api_user.trips.order(started_at: :desc)
    render json: trips.map { |trip| serialize_trip(trip) }
  end

  def show
    trip = current_api_user.trips.find(params[:id])
    render json: serialize_trip(trip)
  end

  def create
    trip = current_api_user.trips.build(trip_params)

    if trip.save
      render json: serialize_trip(trip), status: :ok
    else
      render json: { error: trip.errors.full_messages.join(', ') }, status: :unprocessable_content
    end
  end

  def update
    trip = current_api_user.trips.find(params[:id])

    if trip.update(trip_params)
      render json: serialize_trip(trip), status: :ok
    else
      render json: { error: trip.errors.full_messages.join(', ') }, status: :unprocessable_content
    end
  end

  def destroy
    trip = current_api_user.trips.find(params[:id])

    if trip.destroy
      head :no_content
    else
      render json: { error: 'Failed to delete trip', errors: trip.errors.full_messages }, status: :unprocessable_content
    end
  rescue ActiveRecord::RecordNotFound
    render json: { error: 'Trip not found' }, status: :not_found
  end

  private

  def trip_params
    params.require(:trip).permit(:name, :started_at, :ended_at, :notes)
  end

  def serialize_trip(trip)
    {
      id: trip.id,
      name: trip.name,
      started_at: trip.started_at,
      ended_at: trip.ended_at,
      created_at: trip.created_at,
      updated_at: trip.updated_at
    }
  end
end
