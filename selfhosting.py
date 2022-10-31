import os

import digitalocean
import requests

from core import Treadmill, ValidationError, Validator
from core.tasks import register_action
from core.webapp import app

tm = Treadmill(app, "tasks.yml")


@tm.validator
class check_http_status(Validator):
    def __init__(self, url, expected_status):
        self.url = url
        self.expected_status = expected_status

    def __str__(self):
        return f"Check HTTP status: {self.url} [{self.expected_status}]"

    def validate(self, site):
        url = site.base_url + self.url
        r = requests.get(url)
        if str(r.status_code) != str(self.expected_status):
            raise ValidationError(
                f"For URL {self.url}, actual status code {r.status_code} "
                f"does not match expected status code {self.expected_status}"
            )


@tm.validator
class check_package_exists(Validator):
    def __init__(self, package):
        self.package = package

    def __str__(self):
        return f"Check package exists: {self.package}"

    def validate(self, site):
        r = requests.get(f"{site.base_url}/packages/{self.package}")
        print("status: ", r.status_code)
        print(r.json())
        if r.status_code != 200:
            raise ValidationError(f"Package {self.package} does not exist")


@tm.validator
class check_file_exists(Validator):
    def __init__(self, path):
        self.path = path

    def __str__(self):
        return f"Check file exists: {self.path}"

    def validate(self, app):
        r = requests.get(f"{app.base_url}/{self.path}")
        if r.status_code != 200:
            raise ValidationError(f"File {self.path} does not exist")


@tm.validator
class check_user_exists(Validator):
    def __init__(self, user):
        self.user = user

    def __str__(self):
        return f"Check user exists: {self.user}"

    def validate(self, app):
        r = requests.get(f"{app.base_url}/users")
        r.raise_for_status()

        users = r.json()["data"]["users"]
        if self.user not in users:
            raise ValidationError(f"User {self.user} does not exist")


@register_action
def add_dns_entry(site, task):
    print("action add_dns_entry", site.name, task.name)

    form_values = task.form.get_current_values(site)
    ip_address = form_values["ip"]

    token = os.environ["DIGITALOCEAN_TOKEN"]
    base_domain = tm.config["base_domain"]

    domain = digitalocean.Domain(token=token, name=base_domain)
    for record in domain.get_records():
        if record.name == site.name:
            record.data = ip_address
            record.save()
            break
    else:
        domain.create_new_domain_record(
            type="A",
            name=site.name,
            data=ip_address,
            ttl="120"  # 2 mins, for easy debugging
        )


def main():
    import sys

    cmd = sys.argv[1] if len(sys.argv) > 1 else "run"

    if cmd == "run":
        app.run(debug=True)

    elif cmd == "new":
        site_name = sys.argv[2]
        site = tm.new_site(site_name)
        print(f"Site created: {site.base_url}")

    elif cmd == "check":
        site_name = sys.argv[2]
        site = tm.get_site(site_name)
        if not site:
            print(f"Site not found: {site_name}")
            sys.exit(1)
        status = tm.get_status(site)
        print(status)
        site.update_status(status)

    else:
        print("invalid command: ", cmd)
        sys.exit(1)


if __name__ == "__main__":
    main()
