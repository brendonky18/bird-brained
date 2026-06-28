import argparse
import os
from getpass import getpass

from . import birdalert
from . import ebird


def get_and_update_lists(
    ebird_user: str,
    ebird_pass: str,
    birdalert_user: str,
    birdalert_pass: str,
    region: ebird.Region = ebird.Region.WORLD,
) -> int:
    """Downloads the list of birds seen for the last 6 months, and the life list, and uploads them to birdalerts.info"""
    with ebird.EBirdSession(ebird_user, ebird_pass) as session:
        six_months_birds = list(
            session.get_last_6_months_list(region=ebird.Region(region))
        )
        life_birds = list(session.get_bird_list())

    with birdalert.BirdAlertSession(birdalert_user, birdalert_pass) as ba_session:
        ba_session.upload_list(six_months_birds, f"Last 6 Months ({region.name})")
        ba_session.upload_list(life_birds, f"Life List ({region.proper_name})")

    return 0


def main(argv):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "-r",
        "--region",
        type=ebird.Region,
        choices=[r.value for r in ebird.Region],
        default=ebird.Region.WORLD,
        help="Choose a region to get the list for:\n"
        + ("\n".join([f"  - {r.value}: {r.proper_name}" for r in ebird.Region])),
    )

    args = parser.parse_args(argv)

    get_and_update_lists(
        os.environ.get("EBIRD_USER") or input("EBird username: "),
        os.environ.get("EBIRD_PASS") or getpass("EBird password: "),
        os.environ.get("BIRDALERT_USER") or input("birdalert username: "),
        os.environ.get("BIRDALERT_PASS") or getpass("birdalert password: "),
        region=args.region,
    )


if __name__ == "__main__":
    import sys

    main(sys.argv)
