from django.db import models

# EmployerProfile has been removed — any authenticated user can post a job
# directly (see accounts.CustomUser). This app is kept as an empty shell
# solely so its migration history (CreateModel then DeleteModel) stays
# resolvable for other apps' historical migration dependencies.
