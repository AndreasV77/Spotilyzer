## 0) Voraussetzungen

- **Windows 11**, **PowerShell 7**
    
- **Python 3.12** (Scoop): `scoop install python312`
    
- Virtuelle Umgebung im Projekt: `.venv312/`
    
- Pakete (im venv):
    
    `python -m pip install --upgrade pip setuptools wheel python -m pip install numpy pandas spotipy python-dotenv librosa pyloudnorm`
    

## 1) Projektstruktur (Soll)

`Music Analysis Spotify/ ├─ .venv312/ ├─ .env                     # SPOTIPY_CLIENT_ID=…, SPOTIPY_CLIENT_SECRET=…, SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback ├─ .cache                   # Spotipy-Token ├─ input/                   # Eingaben (IDs, Suchlisten, …) ├─ output/                  # Ergebnisse (alle erzeugten CSVs) ├─ local_audio/             # deine Audiofiles (WAV/MP3) ├─ example_playlist_pull.py ├─ build_genre_ref_stats.py ├─ local_audio_features.py ├─ score_rank.py └─ README.md / RUNBOOK.md`

## 2) Daily Driver – Quick Commands

### venv aktivieren (immer zuerst)

`cd "D:\Software\Audio\Music Analysis Spotify" .\.venv312\Scripts\Activate.ps1 $env:PYTHONNOUSERSITE = "1"`

### 2.1 Playlist → Features CSV

`# Öffentliche Playlist (Client Credentials) python ".\example_playlist_pull.py" --playlist-name "Rock This" --out ".\output\rock_this.csv"  # Mit Market-Filter (für playlist_items, NICHT für audio-features relevant) python ".\example_playlist_pull.py" --playlist-name "Rock This" --market DE --out ".\output\rock_this_DE.csv"  # Falls CC zickt → mit User-Auth (private/collab Playlists & manche Edgecases) python ".\example_playlist_pull.py" --playlist-name "Rock This" -U --out ".\output\rock_this_user.csv"`

> Am Ende erscheint: `Features erhalten: X/Y (ZZ.Z%)` und `OK → …csv (… Zeilen)`.

### 2.2 Lokale MIR-Features (librosa/pyloudnorm)

`python ".\local_audio_features.py" --in ".\local_audio" --out ".\output\local_features.csv"`

### 2.3 Genre-Referenzen bauen (Recommendations, stabil mit CC)

``python ".\build_genre_ref_stats.py" `   --markets DE US GB `   --genres pop rock metal techno house `   --outdir ".\output\refdata"``

Erzeugt u. a.: `.\output\refdata\genre_DE_stats.csv` (mean/std je Feature/Genre).

### 2.4 Scoring / Ranking

``python ".\score_rank.py" `   --local ".\output\local_features.csv" `   --stats ".\output\refdata\genre_DE_stats.csv" `   --out ".\output\ranking_DE.csv"``

- Nutzt Kernfeatures: `tempo, energy, valence, loudness, danceability`
    
- Zuweisung „nächstliegendes Genre-Cluster“, z-Score-Distanz + Kurzdiagnose
    

---

## 3) Auth & Tokens

### `.env` (Beispiel)

`SPOTIPY_CLIENT_ID=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx SPOTIPY_CLIENT_SECRET=yyyyyyyyyyyyyyyyyyyyyyyyyyyy SPOTIPY_REDIRECT_URI=http://127.0.0.1:8888/callback`

**Wichtig:** Redirect **127.0.0.1**, nicht `localhost`.

### Token-Sanity

`python -c 'from dotenv import load_dotenv; load_dotenv(r".\.env"); import spotipy; from spotipy.oauth2 import SpotifyClientCredentials as CC; print(spotipy.Spotify(auth_manager=CC()).auth_manager.get_access_token(as_dict=False)[:40]+"...")'`

---

## 4) Troubleshooting (Kurz & knackig)

### 4.1 401 Unauthorized

- `.env` prüfen (ID/Secret korrekt?)
    
- Uhrzeit/Datum des Systems ok?
    
- Bei `-U`: Redirect-URI stimmt? Nutzer hat Zugriff auf die Playlist?
    

### 4.2 403 Forbidden (Audio Features)

- Kommt sporadisch, v. a. im CC-Flow.
    
- In `example_playlist_pull.py`:
    
    - Audio-Features werden **chunked** (100er), bei 403 → **Einzel-ID-Fallback**.
        
    - Coverage-Zeile zeigt, wie viel gerettet wurde.
        
- Workarounds:
    
    - Ohne `--market` erneut probieren
        
    - Mit `-U` laufen
        
    - Andere Owner=Spotify-Playlist testweise ziehen (um problematische IDs zu isolieren)
        

### 4.3 404 Not Found

- **Playlist-ID prüfen** (22 Zeichen) oder bei Name-Suche:
    
    - Funktion nutzt Owner-Filter `spotify`, paginiert & guardet `None`.
        
- **Ganz wichtig:** Endpoints für Audio-Features heißen:
    
    - Pfad: `audio-features` (Bindestrich!)
        
    - JSON-Key: `audio_features` (Unterstrich!)  
        Vertauschen führt zu leeren Ergebnissen/404.
        

### 4.4 NameResolutionError / DNS / Proxy

- Session-Umgebungsvariablen prüfen:
    
    `Get-ChildItem Env: | ? { $_.Name -match 'proxy|REQUESTS|CURL|SSL' } Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY -ErrorAction SilentlyContinue $env:NO_PROXY = "127.0.0.1,localhost,.spotify.com"`
    
- Curl-Gegentest:
    
    ``# CC-Token holen $cid = (Select-String .\.env '^SPOTIPY_CLIENT_ID=(.*)$').Matches[0].Groups[1].Value $sec = (Select-String .\.env '^SPOTIPY_CLIENT_SECRET=(.*)$').Matches[0].Groups[1].Value $b64 = [Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes("$cid`:$sec")) $tok = curl -s -X POST "https://accounts.spotify.com/api/token" -H "Authorization: Basic $b64" -H "Content-Type: application/x-www-form-urlencoded" --data "grant_type=client_credentials" | ConvertFrom-Json $ids = "11dFghVXANMlKmJXsNCbNl" curl -s "https://api.spotify.com/v1/audio-features?ids=$ids" -H "Authorization: Bearer $($tok.access_token)" | ConvertFrom-Json``
    

### 4.5 venv-Verwirrung (Matroschka)

- Immer **nur** `.\.venv312\` im Root.
    
- Aktiv: `.\.venv312\Scripts\Activate.ps1`
    
- Prüfen:
    
    `$env:VIRTUAL_ENV Get-Command python | select Source Get-Command pip | select Source`
    

---

## 5) Empfehlungen

### Playlists vs. Recommendations

- Wenn Playlist-Endpunkte/Features „zicken“ (403):  
    **Standard-Referenzen** über `build_genre_ref_stats.py` (seed_genres) nutzen.  
    Stabil mit Client Credentials, optional je Markt **DE/US/GB** getrennt → `refdata/`.
    

### Scoring robust halten

- `score_rank.py` rechnet automatisch mit der **Schnittmenge** der verfügbaren Features.
    
- Fehlende Spotify-Features blockieren das Ranking **nicht**.
    

### PowerShell Zeilenumbruch

- In pwsh: **Backtick** für multiline:
    
    ``python ".\build_genre_ref_stats.py" `   --markets DE US GB `   --genres pop rock metal techno house `   --outdir ".\output\refdata"``
    

---

## 6) Typische Fehlerbilder → schnelle Fixes

|Symptom|Ursache|Fix|
|---|---|---|
|`AttributeError: 'NoneType' object has no attribute 'get'` bei Suche|Spotify-Suche liefert `None`-Items|**Robuste** `find_spotify_playlist_id` verwenden (ist im Script)|
|`KeyError: ['id']` beim Merge|Feature-Frame leer|Guard drin lassen (`if "id" in fdf.columns: … else:`)|
|Viele `403` in `/audio-features`|Ratelimit/Edgecase|Ohne `--market`, später `-U`, Einzel-ID-Fallback im Script|
|`NameResolutionError`|Proxy/DNS-Env stört|Env bereinigen (siehe 4.4), Curl-Gegentest|
|`ImportError` NumPy/numba|Python 3.14 Wheels fehlen|**Python 3.12 venv** benutzen|

---

## 7) Mini-FAQ

**Q:** Kann ich Scoring ohne Spotify-Features fahren?  
**A:** Ja. `local_features.csv` + `genre_*_stats.csv` reichen. Sobald Playlist-Features da sind, kannst du weitere Diagnosen/Cluster fahren.

**Q:** Private Playlist?  
**A:** `-U` verwenden (Authorization Code Flow) und in der Spotify Dev App den Nutzer freischalten.

**Q:** Wo landen Ergebnisse?  
**A:** In `.\output\`. Referenzdaten unter `.\output\refdata\*`.