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
    search_str: ebird.Region | str = ebird.MajorRegion.WORLD,
    cache: Path | None = None,
) -> int:
    """Downloads the list of birds seen for the last 6 months, and the life list, and uploads them to birdalerts.info"""
    with ebird.EBirdSession(ebird_user, ebird_pass, cache=cache) as session:
        if isinstance(search_str, str):
            region = session.get_region(search_str)
        else:
            region = search_str

        six_months_birds = list(session.get_last_6_months_list(region=region))
        # TODO: check if the correct time span is being applied for the list
        # TODO: add logging
        life_birds = list(
            session.get_bird_list(
                query=ebird.BirdListQuery(region=region, _time="life")
            )
        )

    with birdalert.BirdAlertSession(birdalert_user, birdalert_pass) as ba_session:
        ba_session.upload_list(
            six_months_birds, f"Last 6 Months ({region.proper_name})"
        )
        sleep(1)
        ba_session.upload_list(life_birds, f"Life List ({region.proper_name})")

    return 0


def main(argv):
    parser = argparse.ArgumentParser(formatter_class=argparse.RawTextHelpFormatter)
    location_mutex_group = parser.add_mutually_exclusive_group()
    location_mutex_group.set_defaults(region=ebird.MajorRegion.WORLD, search_str=None)
    location_mutex_group.add_argument(
        "-R",
        "--major-region",
        type=ebird.MajorRegion,
        choices=list(ebird.MajorRegion),
        help="Choose a region to get the list for:\n"
        + ("\n".join([f"  - {r.value}: {r.proper_name}" for r in ebird.MajorRegion])),
    )
    location_mutex_group.add_argument(
        "-r",
        "--region",
        type=str,
        dest="search_str",
        help="Enter the name of an eBird region",
    )
    location_mutex_group.add_argument(
        "-l",
        "--personal-location",
        type=str,
        dest="search_str",
        help="Enter the name of one of your personal locations from eBird",
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

    # FIXME: searching for a personal location returns a region, because they are submitting the same query
    # I need to figure out how to separate personal location queries from region queries, and then perform the different request
    if args.search_str is not None:
        region = args.search_str
    else:
        region = args.region

    get_and_update_lists(
        ebird_user,
        ebird_pass,
        birdalert_user,
        birdalert_pass,
        search_str=region,
        cache=args.cache,
    )


if __name__ == "__main__":
    import sys

    main(sys.argv[1:])
