import argparse
import os
from getpass import getpass
from pathlib import Path
from time import sleep

from . import birdalert
from . import ebird


def get_and_update_lists(
    ebird_user: str,
    ebird_pass: str,
    birdalert_user: str,
    birdalert_pass: str,
    use_location: tuple[ebird.LocationType, str] = (
        ebird.LocationType.MAJOR_REGION,
        ebird.MajorRegion.WORLD.code,
    ),
    cache: Path | None = None,
) -> int:
    """Downloads the list of birds seen for the last 6 months, and the life list, and uploads them to birdalerts.info"""
    with ebird.EBirdSession(ebird_user, ebird_pass, cache=cache) as session:
        if isinstance(use_location, ebird.Location):
            location = use_location
        elif use_location[0] == ebird.LocationType.MAJOR_REGION:
            location = session.get_major_region(use_location[1])
        elif use_location[0] == ebird.LocationType.REGION:
            location = session.get_region(use_location[1])
        elif use_location[0] == ebird.LocationType.LOCATION:
            location = session.get_personal_location(use_location[1])
        else:
            raise ValueError(f"{use_location}: unknown location parameter")

        six_months_birds = list(session.get_last_6_months_list(region=location))
        life_birds = list(
            session.get_bird_list(query=ebird.BirdListQuery(location=location))
        )

    with birdalert.BirdAlertSession(birdalert_user, birdalert_pass) as ba_session:
        ba_session.upload_list(
            six_months_birds, f"Last 6 Months ({location.proper_name})"
        )
        sleep(1)
        ba_session.upload_list(life_birds, f"Life List ({location.proper_name})")

    return 0


def main(argv):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    location_mutex_group = parser.add_mutually_exclusive_group()
    location_mutex_group.add_argument(
        "-R",
        "--major-region",
        type=str,
        default=ebird.MajorRegion.WORLD.code,
        help="Choose a region to get the list for:\n"
        + ("\n".join([f"  - {r.code}: {r.proper_name}" for r in ebird.MajorRegion])),
    )
    location_mutex_group.add_argument(
        "-r",
        "--region",
        type=str,
        default=None,
        help="Enter the name of an eBird region",
    )
    location_mutex_group.add_argument(
        "-l",
        "--location",
        type=str,
        default=None,
        help="Enter the name of a hotspot, or one of your personal locations",
    )

    parser.add_argument(
        "-d",
        "--headless",
        action="store_true",
        help="Don't prompt the user for login credentials.\n"
        "Credentials must be provided in environment variables, or the program will exit.",
    )
    parser.add_argument(
        "-c",
        "--cache",
        type=Path,
        help="Path to the cache directory.",
        default=None,
    )

    args = parser.parse_args(argv)

    ebird_user = os.environ.get("EBIRD_USER")
    ebird_pass = os.environ.get("EBIRD_PASS")
    birdalert_user = os.environ.get("BIRDALERT_USER")
    birdalert_pass = os.environ.get("BIRDALERT_PASS")

    if ebird_user is None:
        if args.headless:
            raise RuntimeError("EBird username not found")
        ebird_user = input("EBird username: ")
    if ebird_pass is None:
        if args.headless:
            raise RuntimeError("EBird password not found")
        ebird_pass = getpass("EBird password: ")
    if birdalert_user is None:
        if args.headless:
            raise RuntimeError("birdalert username not found")
        birdalert_user = input("birdalert username: ")
    if birdalert_pass is None:
        if args.headless:
            raise RuntimeError("birdalert password not found")
        birdalert_pass = getpass("birdalert password: ")

    if args.location is not None:
        location = (ebird.LocationType.LOCATION, args.location)
    elif args.region is not None:
        location = (ebird.LocationType.REGION, args.region)
    else:
        location = (ebird.LocationType.MAJOR_REGION, args.major_region)

    get_and_update_lists(
        ebird_user,
        ebird_pass,
        birdalert_user,
        birdalert_pass,
        use_location=location,
        cache=args.cache,
    )


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
