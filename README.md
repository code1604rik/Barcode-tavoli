# Barcode — Gestione Tavoli

Web app per segnare lo stato dello scontrino POS di 50 tavoli del bar.

Ogni tavolo, a ogni clic, cambia stato in ciclo:

`Normale → Scontrino emesso → Incassato → Normale`

Lo stato è condiviso tra tutti i dispositivi e si aggiorna ogni 4 secondi.

## Avvio in locale
```
pip install -r requirements.txt
python app.py
```
Apri http://localhost:8000

## Deploy su Railway
Il `Procfile` avvia l'app con gunicorn (1 worker, così lo stato resta coerente).

### Variabili d'ambiente (Railway → Variables)
| Variabile     | A cosa serve                                  | Esempio                     |
|---------------|-----------------------------------------------|-----------------------------|
| `APP_PASSWORD`| Password del personale per il login           | `code2025`                  |
| `SECRET_KEY`  | Chiave per firmare le sessioni (stringa lunga)| `f8a3...stringa-casuale`    |
| `NUM_TAVOLI`  | (Opzionale) Numero di tavoli                  | `50`                        |
| `STATO_FILE`  | (Opzionale) Percorso file stato               | `/data/stato_tavoli.json`   |

## Stati e colori
- **Normale** — grigio (nessuno scontrino)
- **Scontrino emesso** — ambra
- **Incassato** — verde
