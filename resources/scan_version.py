import boto3
import random
import datetime
from decimal import Decimal

client = boto3.resource("dynamodb", region_name="eu-central-1")
events = client.Table("cosmin-edr-vehicle")
incidents = client.Table("cosmin-edr-radar")


event_type_list = ["rapid acc", "rapid dec", "dtc event"]
brake_status_list = ["applied", "released"]
seatbelt_status_list = ["locked", "unlocked"]

object_type_list = ["vehicle", "pedestrian", "cyclist", "tree", "sign"]
object_size_list = ["small", "medium", "large"]
object_class_list = ["car", "truck", "motorcycle"]


def generate_vehicle_base_data():
    return {
        "base_speed": random.randint(50, 100),
        "base_fuel_level": random.randint(30, 80),
        "base_rpm": random.randint(1500, 3000),
        "base_throttle_position": random.randint(30, 70),
        "acceleration": {"x": random.uniform(-2, 2), "y": random.uniform(-1, 1), "z": 9.8},
        "location": {"latitude": random.uniform(37.0, 38.0), "longitude": random.uniform(-122.5, -122.0)},
    }


def generate_events(vehicle_id, vehicle_base_data, num_events=100):
    events_to_insert = []
    for i in range(num_events):
        event_timestamp = datetime.datetime.now() - datetime.timedelta(seconds=i * 10)
        event_timestamp_str = event_timestamp.strftime("%Y-%m-%dT%H:%M:%SZ")

        events_to_insert.append(
            {
                "vehicle_id": f"vehicle_{vehicle_id}",
                "event_id": f"event_id_{vehicle_id}_{i}",
                "timestamp": event_timestamp_str,
                "event_type": random.choice(event_type_list),
                "acceleration": {
                    "x": Decimal(str(vehicle_base_data["acceleration"]["x"] + random.uniform(-0.5, 0.5))).quantize(Decimal('0.00')),
                    "y": Decimal(str(vehicle_base_data["acceleration"]["y"] + random.uniform(-0.2, 0.2))).quantize(Decimal('0.00')),
                    "z": Decimal("9.8"),
                },
                "location": {
                    "latitude": Decimal(str(vehicle_base_data["location"]["latitude"] + random.uniform(-0.01, 0.01))).quantize(Decimal('0.0')),
                    "longitude": Decimal(str(vehicle_base_data["location"]["longitude"] + random.uniform(-0.01, 0.01))).quantize(Decimal('0.00')),
                },
                "vehicle_speed": vehicle_base_data["base_speed"] + random.randint(-5, 5),
                "fuel_level": vehicle_base_data["base_fuel_level"] + random.randint(-3, 3),
                "engine_rpm": vehicle_base_data["base_rpm"] + random.randint(-200, 200),
                "throttle_position": vehicle_base_data["base_throttle_position"] + random.randint(-5, 5),
                "brake_status": random.choice(brake_status_list),
                "seatbelt_status": random.choice(seatbelt_status_list),
                "airbag_deployed": random.choice([True, False]),
                "error_codes": [f"P{random.randint(100, 999)}", f"P{random.randint(100, 999)}"],
            }
        )

    with events.batch_writer() as batch:
        for event in events_to_insert:
            batch.put_item(Item=event)


def generate_incidents(vehicle_id, incident_timestamp, num_incidents=800):
    radar_data_to_insert = []
    for i in range(num_incidents):
        radar_timestamp = incident_timestamp + datetime.timedelta(milliseconds=i)
        radar_timestamp_str = radar_timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ")[:-3]

        radar_data_to_insert.append(
            {
                "event_id": f"event_id_{vehicle_id}_{i}",
                "timestamp": radar_timestamp_str,
                "radar_id": f"RADAR_{i + 1}",
                "distance": Decimal(str(random.uniform(1, 100))).quantize(Decimal('0.00')),
                "velocity": Decimal(str(random.uniform(1, 50))).quantize(Decimal('0.00')),
                "azimuth_angle": random.randint(0, 360),
                "elevation_angle": random.randint(0, 90),
                "object_type": random.choice(object_type_list),
                "object_size": random.choice(object_size_list),
                "object_class": random.choice(object_class_list),
                "confidence_level": Decimal(str(random.uniform(0.5, 1.0))).quantize(Decimal('0.00')),
            }
        )

    with incidents.batch_writer() as batch:
        for radar_data in radar_data_to_insert:
            batch.put_item(Item=radar_data)


def generate_data_for_multiple_vehicles(num_vehicles=100, num_incidents_per_vehicle=100, num_radar_readings_per_incident=800):
    for vehicle_id in range(1, num_vehicles + 1):
        print(f"Generating data for Vehicle {vehicle_id}...")
        vehicle_base_data = generate_vehicle_base_data()
        for incident_id in range(num_incidents_per_vehicle):
            generate_events(vehicle_id, vehicle_base_data, num_events=random.randint(1, 5))

            incident_timestamp = datetime.datetime.now() - datetime.timedelta(seconds=incident_id * 10)
            generate_incidents(vehicle_id, incident_timestamp, num_incidents=num_radar_readings_per_incident)


def delete_vehicle_data(vehicle_id):
    response = events.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('vehicle_id').eq(f"vehicle_{vehicle_id}")
    )

    with events.batch_writer() as batch:
        for item in response['Items']:
            batch.delete_item(
                Key={
                    'vehicle_id': item['vehicle_id'],
                    'event_id': item['event_id']
                }
            )

    response = incidents.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('event_id').begins_with(f"event_id_{vehicle_id}_")
    )

    with incidents.batch_writer() as batch:
        for item in response['Items']:
            batch.delete_item(
                Key={
                    'event_id': item['event_id'],
                    'radar_id': item['radar_id']
                }
            )

    print(f"Deleted all events and radar incidents for vehicle_{vehicle_id}.")

def filter_incidents(vehicle_id):
    response = incidents.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('event_id').begins_with(f"event_id_{vehicle_id}_")
    )

    #filter the incidents based on object_type and confidence_level
    filtered_incidents = [
        item for item in response['Items']
        if item['object_type'] in ["vehicle", "pedestrian", "cyclist"] and item['confidence_level'] > Decimal('0.80')
    ]

    if not filtered_incidents:
        print('No incidents found for that vehicle')
    else:
        for incident in filtered_incidents:
            print(incident)

def detect_accidents(vehicle_id):
    response = events.scan(
        FilterExpression=boto3.dynamodb.conditions.Attr('vehicle_id').eq(f"vehicle_{vehicle_id}")
    )

    event_items = sorted(response['Items'], key=lambda x: x['timestamp'])

    potential_accidents = []

    for i in range(1, len(event_items)):
        prev_event = event_items[i - 1]
        curr_event = event_items[i]
        prev_timestamp = datetime.datetime.strptime(prev_event['timestamp'], "%Y-%m-%dT%H:%M:%SZ")
        curr_timestamp = datetime.datetime.strptime(curr_event['timestamp'], "%Y-%m-%dT%H:%M:%SZ")

        time_difference = (curr_timestamp - prev_timestamp).total_seconds()

        if time_difference <= 2:

            prev_speed = prev_event['vehicle_speed']
            curr_speed = curr_event['vehicle_speed']


            if prev_speed >= 30 and curr_speed == 0:
                potential_accidents.append(curr_event)

    if potential_accidents:
        print(f"Potential accidents detected for vehicle_{vehicle_id}:")
        for accident in potential_accidents:
            print(accident)
    else:
        print(f"No potential accidents detected for vehicle_{vehicle_id}.")


if __name__ == "__main__":
    #generate_data_for_multiple_vehicles(10, 3, 3)
    #delete_vehicle_data(6) #error but works :D
    #filter_incidents(10)
    detect_accidents(5)

