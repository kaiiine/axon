"""La marketplace d'Axon : catalogue, installation et registre des plugins.

Un plugin est un dépôt git (ou un sous-dossier de dépôt) qui porte un
`plugin.json`. Il s'installe dans `~/.axon/plugins/<id>` ; le cœur ne le
connaît que par les capacités qu'il déclare (`ile`, `notifications`…).

Bibliothèque standard uniquement : le démon cron consulte le registre.
"""
