"""Script demonstrating how to use Apitit and store retrieved data in an InfluxDB.

It is assumed this script is called regularly, hence the data query is limited to the
last two days. If the same data is written again to InfluxDB, it doesn't duplicate the
data, so there's no need to account for that.

Tested with InfluxDB 2.0.
The following additional Python dependencies have to be installed:
* influxdb-client
* pyaml

It is assumed the configuration is stored in the file ``config.yml``::

    influx:
        url: <InfluxDB URL>
        token: <Access token>
        org: <Organization name>
        bucket: <Bucket name>
    apitit:
        location: <Location>
        card_number: <Card number>
        password: <Password belonging to card_number>

"""
import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
import yaml

from apitit import Apitit


CONFIG_FILE = Path(__file__).parent / "config.yml"


def transactions_as_influx_dict(transactions):
    """Rewrite transactions as dict compatible to influxdb-client's WriteApi.write.

    Args:
        transactions (list of dicts): Transactions as returned by
            Apitit.get_transactions

    Returns:
        List of InfluxDB-compatible dicts.
    """
    out = []
    for transaction in transactions:
        # Convert time to utc timestamp
        utc_timestamp = datetime.datetime.strptime(
            transaction["datum"], "%d.%m.%Y %H:%M"
        ).replace(tzinfo=ZoneInfo("Europe/Berlin"))
        utc_timestamp = int(utc_timestamp.timestamp())
        data = {
            "measurement": "transactions",
            "time": utc_timestamp,
            "tags": {
                "location": transaction["ortName"],
                "type": transaction["typName"],
            },
            "fields": {
                # Ensure amount is a float to prevent type conflicts with influxdb
                "amount": float(transaction["zahlBetrag"]),
                "point_of_sale": transaction["kaName"],
            },
        }
        out.append(data)
    return out


def positions_as_influx_dict(transaction_positions, transactions):
    """Rewrite positions as dict compatible to influxdb-client's WriteApi.write.

    Note that transaction_positions do not include timestamps, but a reference to the
    transaction. Hence transactions are required to be able to look up the corresponding
    times.

    Args:
        transaction_positions (list of dicts): Transaction positions as returned by
            Apitit.get_transaction_positions
        transactions (list of dicts): Transactions as returned by
            Apitit.get_transactions

    Returns:
        List of InfluxDB-compatible dicts.
    """
    # Create time lookup dict from transactions
    trans_id_times = {}
    for transaction in transactions:
        # Convert time to utc timestamp
        utc_timestamp = datetime.datetime.strptime(
            transaction["datum"], "%d.%m.%Y %H:%M"
        ).replace(tzinfo=ZoneInfo("Europe/Berlin"))
        utc_timestamp = int(utc_timestamp.timestamp())
        trans_id_times[transaction["transFullId"]] = utc_timestamp

    out = []
    for trans_pos in transaction_positions:
        data = {
            "measurement": "transaction_positions",
            "time": trans_id_times[trans_pos["transFullId"]],
            "tags": {
                "name": trans_pos["name"],
            },
            "fields": {
                "position": trans_pos["posId"],
                "quantity": trans_pos["menge"],
                # Ensure prices are floats to prevent type conflicts
                "unit_price": float(trans_pos["epreis"]),
                "total_price": float(trans_pos["gpreis"]),
                "rating": trans_pos["bewertung"],
            },
        }
        if "rabatt" in trans_pos:
            data["fields"]["discount"] = float(trans_pos["rabatt"])
        out.append(data)

    return out


if __name__ == "__main__":
    if CONFIG_FILE.is_file:
        with open(CONFIG_FILE, "r") as f:
            config = yaml.safe_load(f)
    else:
        raise IOError("Config file not found.")

    # Get data via Apitit
    apt = Apitit(
        location=config["apitit"]["location"],
        card_number=config["apitit"]["card_number"],
        user_password=config["apitit"]["password"],
    )
    to_date = datetime.date.today()
    from_date = to_date - datetime.timedelta(days=2)
    trans = apt.get_transactions(from_date, to_date)
    pos = apt.get_transaction_positions(from_date, to_date)

    # Cast to InfluxDB-compatible data
    db_trans = transactions_as_influx_dict(trans)
    db_pos = positions_as_influx_dict(pos, trans)

    # Write to InfluxDB
    client = InfluxDBClient(
        url=config["influx"]["url"],
        token=config["influx"]["token"],
        org=config["influx"]["org"],
    )
    write_api = client.write_api(write_options=SYNCHRONOUS)

    write_api.write(
        bucket=config["influx"]["bucket"], record=db_trans, write_precision="s"
    )
    write_api.write(
        bucket=config["influx"]["bucket"], record=db_pos, write_precision="s"
    )
