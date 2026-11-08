## TravelMatch (Junior Seminar Prototype)

This is a prototype implementation of **TravelMatch**, a web platform that helps users
find compatible travel buddies and manage basic group trip information.

This codebase focuses on the **first ~50% of the project**:

- **User accounts**: sign up, login, logout (using Django's auth system)
- **Travel profiles**: each user can store travel preferences such as destination,
  budget range, dates, and travel style
- **Simple matching**: dashboard shows suggested travel buddies with overlapping
  destinations or styles
- **Group trips**: users can create trips, join existing trips, and see members

Later phases (not yet implemented) would add:

- Group chat/messaging
- Collaborative itinerary builder
- Detailed expense splitting and balances

### Tech stack

- Django 4.2 (Python web framework)
- SQLite (default Django database)
- HTML templates with Bootstrap 5 for a clean UI

### How to run the project locally

From the `travelmatch` folder:

```bash
cd travelmatch
python3 -m venv venv
source venv/bin/activate  # On Windows use: venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```
``` lsof -ti :8000 | xargs kill -9 2>/dev/null; echo "done" ```

Then visit `http://127.0.0.1:8000/` in your browser.

For deployment, set the `DJANGO_SECRET_KEY` environment variable to a unique,
random secret. The default key is for local development only. The local SQLite
database, virtual environments, and `.env` files are excluded from Git.

### Key URLs / pages

- `/` – Home page with project description and a list of recent trips
- `/accounts/signup/` – User registration
- `/accounts/login/` – Login
- `/dashboard/` – Logged-in user's dashboard:
  - Edit travel profile/preferences
  - View suggested travel buddies
  - View and access your trips
- `/trips/` – List of all trips
- `/trips/create/` – Create a new trip
- `/trips/<id>/` – View a specific trip and join it

### How this maps to the proposal

- **User registration & profile creation**: implemented via signup and profile forms.
- **Preference-based matching**: basic matching logic on destination and travel style,
  displayed as "Suggested travel buddies" on the dashboard.
- **Group formation**: users can create trips and join existing trips, forming travel groups.
- **Trip management basics**: trip list and detail pages show essential information and members.

These pieces provide a solid, working baseline that can be demonstrated as a partially
completed TravelMatch system for the junior seminar project.
