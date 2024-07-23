from datetime import datetime, timedelta, timezone

from grist_api import GristDocAPI


class TchapIam:
    REFRESH_DELTA = 3600
    TZ = timezone(timedelta(hours=2))

    def __init__(self, config):
        self.config = config
        self.users_table_id = config.grist_users_table_id
        self.users_table_name = config.grist_users_table_name
        self.iam_client = GristDocAPI(
            self.users_table_id,
            server=config.grist_api_server,
            api_key=config.grist_api_key,
        )
        self.users_allowed = {}
        self.last_refresh = None
        self._refresh()

    def _refresh(self):
        ttl = datetime.utcnow() - timedelta(seconds=self.REFRESH_DELTA)
        if not self.last_refresh or self.last_refresh < ttl:
            users_table = self.iam_client.fetch_table(
                self.users_table_name, filters={"status": "allowed"}
            )
            self.users_allowed.clear()
            for record in users_table:
                self.users_allowed[record.tchap_user] = record

            self.last_refresh = datetime.utcnow()
            print("User table (IAM) updated")

    def is_user_allowed(self, username):
        self._refresh()
        return username in self.users_allowed

    def increment_user_question(self, username, n=1, update_last_activity=True):
        try:
            record = self.users_allowed[username]
        except Exception as err:
            raise ValueError("User not found in grist") from err

        updates = {"n_questions": record.n_questions + n}
        if update_last_activity:
            updates["last_activity"] = datetime.now(self.TZ)

        self.iam_client.update_records(
            self.users_table_name, [{"id": record.id, **updates}]
        )

        self.users_allowed[username] = record._replace(**updates)

