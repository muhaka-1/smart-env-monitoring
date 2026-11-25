"""Valfri AI-funktionalitet med lokal modell (Ollama).

Avvikelsedetektionen (``anomaly``) är ren statistik och kräver ingen modell.
Textfunktionerna (``summary``, ``explain``) är avstängda som standard och
faller alltid tillbaka på en vanlig text om modellen saknas eller svarar fel.
"""
