#!/usr/bin/env python3
"""Overlay d'Axon pour Hyprland.

Une petite île en haut de l'écran : la mascotte, ce qu'Axon fait, les demandes
de confirmation et un champ pour lui écrire.

Pile : GTK4 + gtk4-layer-shell (la fenêtre devient une couche Wayland ancrée en
haut de l'écran) + WebKitGTK (l'interface est une page HTML, ce qui permet de
réutiliser les SVG animés du kit tels quels).

Axon se connecte au socket Unix de l'overlay et y écrit du JSON, une ligne par
message. L'overlay répond sur la même connexion (décisions, commandes).

Lancer :
    LD_PRELOAD=/usr/lib/libgtk4-layer-shell.so python overlay.py

Le LD_PRELOAD est obligatoire en Python : gtk4-layer-shell doit être chargé
avant libwayland, sinon la fenêtre s'ouvre comme une fenêtre normale.
"""
from __future__ import annotations

import json
import os
import signal
import socket
import threading
from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Gdk", "4.0")
gi.require_version("WebKit", "6.0")
gi.require_version("Gtk4LayerShell", "1.0")
gi.require_version("Graphene", "1.0")
gi.require_version("Gsk", "4.0")
from gi.repository import Gdk, GLib, Gtk, WebKit, Gsk, Graphene  # noqa: E402
from gi.repository import Gtk4LayerShell as LayerShell  # noqa: E402

ICI = Path(__file__).resolve().parent
RUNTIME = Path(os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))
SOCKET = RUNTIME / "axon" / "overlay.sock"
# Canal de contrôle (rappels du démon, bascule) : à part, car `overlay.sock`
# n'accepte qu'UN client — le CLI — et toute autre connexion l'éjecterait.
SOCKET_CONTROLE = RUNTIME / "axon" / "controle.sock"

# Deux tailles natives. Aucun remappage ou rechargement lors du changement de vue.
TAILLE_ACCUEIL = (780, 280)
TAILLE_DETAIL = (780, 500)
# Une demande HITL qui arrive île fermée : une petite notification, pas le chat.
TAILLE_NOTIF = (620, 152)
# La notification suit la hauteur de son contenu (plusieurs lignes de
# réponses), dans ces bornes ; au-delà, elle défile.
HAUTEUR_NOTIF = (120, 340)
# Avant le survol, juste Axon dans une petite bulle de verre, collée sous la barre.
TAILLE_PASTILLE = (44, 44)
MARGE_HAUT = 14
MARGE_HAUT_PASTILLE = 6
TAILLES = {"accueil": TAILLE_ACCUEIL, "detail": TAILLE_DETAIL, "notif": TAILLE_NOTIF,
           "bulle": TAILLE_NOTIF, "pastille": TAILLE_PASTILLE}
# La notification d'une demande et la bulle d'un rappel suivent leur contenu.
HAUTEUR_VARIABLE = {"notif", "bulle"}
# La pastille et la bulle ne font qu'annoncer : avec le clavier, leur apparition
# volait le focus au terminal — les flèches d'un /backend ne répondaient plus
# tant que la souris n'avait pas bougé. Leurs boutons restent cliquables.
SANS_CLAVIER = {"pastille", "bulle"}


class PontSocket:
    """Serveur Unix. Un seul client à la fois : Axon.

    La lecture tourne dans un thread ; chaque message est renvoyé au thread GTK
    avec GLib.idle_add, car on ne touche jamais l'interface depuis un autre thread.
    """

    def __init__(self, chemin: Path, sur_message):
        self.chemin = chemin
        self.sur_message = sur_message
        self.client: socket.socket | None = None
        self.verrou = threading.Lock()

    def demarrer(self) -> None:
        # Dossier en 0700 et socket en 0600 : seul ton utilisateur peut s'y connecter.
        self.chemin.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.chemin.unlink(missing_ok=True)
        serveur = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        serveur.bind(str(self.chemin))
        os.chmod(self.chemin, 0o600)
        serveur.listen(1)
        threading.Thread(target=self._accepter, args=(serveur,), daemon=True).start()

    def _accepter(self, serveur: socket.socket) -> None:
        while True:
            client, _ = serveur.accept()
            with self.verrou:
                if self.client is not None:
                    self.client.close()
                self.client = client
            GLib.idle_add(self.sur_message, {"type": "connexion", "connecte": True})
            self._lire(client)

    def _lire(self, client: socket.socket) -> None:
        try:
            with client.makefile("r", encoding="utf-8") as flux:
                for ligne in flux:
                    try:
                        message = json.loads(ligne)
                    except json.JSONDecodeError:
                        continue
                    GLib.idle_add(self.sur_message, message)
        except OSError:
            pass
        finally:
            with self.verrou:
                if self.client is client:
                    self.client = None
            GLib.idle_add(self.sur_message, {"type": "connexion", "connecte": False})

    def envoyer(self, message: dict) -> bool:
        with self.verrou:
            if self.client is None:
                return False
            try:
                ligne = json.dumps(message, ensure_ascii=False) + "\n"
                self.client.sendall(ligne.encode("utf-8"))
                return True
            except OSError:
                return False


class CanalControle:
    """Serveur Unix des messages ponctuels : plusieurs expéditeurs, chacun
    envoie ses lignes JSON puis se déconnecte. Seuls `rappel` et `basculer`
    sont acceptés — ce canal ne pilote rien d'autre dans l'île."""

    TYPES = ("rappel", "basculer")

    def __init__(self, chemin: Path, sur_message):
        self.chemin = chemin
        self.sur_message = sur_message

    def demarrer(self) -> None:
        self.chemin.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        self.chemin.unlink(missing_ok=True)
        serveur = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        serveur.bind(str(self.chemin))
        os.chmod(self.chemin, 0o600)
        serveur.listen(4)
        threading.Thread(target=self._accepter, args=(serveur,), daemon=True).start()

    def _accepter(self, serveur: socket.socket) -> None:
        while True:
            client, _ = serveur.accept()
            threading.Thread(target=self._lire, args=(client,), daemon=True).start()

    def _lire(self, client: socket.socket) -> None:
        client.settimeout(5)
        try:
            with client, client.makefile("r", encoding="utf-8") as flux:
                for ligne in flux:
                    try:
                        message = json.loads(ligne)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(message, dict) and message.get("type") in self.TYPES:
                        GLib.idle_add(self.sur_message, message)
        except OSError:
            pass


class CadreArrondi(Gtk.Box):
    """Clip GTK réel, y compris le fond opaque éventuel de WebKit."""

    def __init__(self, enfant):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_overflow(Gtk.Overflow.HIDDEN)
        enfant.set_hexpand(True)
        enfant.set_vexpand(True)
        self.append(enfant)

    def do_snapshot(self, snapshot):
        rect = Graphene.Rect()
        rect.init(0, 0, self.get_width(), self.get_height())
        arrondi = Graphene.Size()
        arrondi.init(32, 32)
        clip = Gsk.RoundedRect()
        clip.init(rect, arrondi, arrondi, arrondi, arrondi)
        snapshot.push_rounded_clip(clip)
        enfant = self.get_first_child()
        if enfant is not None:
            self.snapshot_child(enfant, snapshot)
        snapshot.pop()


class Overlay(Gtk.Application):
    def __init__(self):
        super().__init__(application_id="fr.axon.overlay")
        self.ouvert = False
        self.page_prete = False
        self.attente = []
        self.mode = "accueil"
        self.taille = TAILLE_ACCUEIL
        self.hauteur_notif = TAILLE_NOTIF[1]
        self.synchronisation = False
        self.generation = 0

    def do_activate(self):
        if hasattr(self, "fenetre"):
            self.basculer()
            return
        if not (ICI / "ui/dist/axon.js").is_file():
            raise RuntimeError("Front compilé absent. Exécute npm ci puis npm run build dans axon-overlay.")
        self.hold()
        self.fenetre = Gtk.ApplicationWindow(application=self)
        self.fenetre.set_decorated(False)
        self.fenetre.add_css_class("axon-window")
        LayerShell.init_for_window(self.fenetre)
        LayerShell.set_namespace(self.fenetre, "axon-overlay")
        LayerShell.set_layer(self.fenetre, LayerShell.Layer.TOP)
        LayerShell.set_anchor(self.fenetre, LayerShell.Edge.TOP, True)
        LayerShell.set_margin(self.fenetre, LayerShell.Edge.TOP, MARGE_HAUT)
        LayerShell.set_keyboard_mode(self.fenetre, LayerShell.KeyboardMode.ON_DEMAND)
        contenu = WebKit.UserContentManager()
        contenu.register_script_message_handler("axon", None)
        contenu.connect("script-message-received::axon", self.depuis_page)
        self.vue = WebKit.WebView(user_content_manager=contenu)
        self.vue.set_background_color(Gdk.RGBA(red=0, green=0, blue=0, alpha=0))
        self.vue.connect("web-process-terminated", self.processus_termine)
        self.vue.connect("load-failed", self.chargement_echoue)
        self.vue.set_size_request(*TAILLE_ACCUEIL)
        depose = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        depose.connect("drop", self._sur_depot)
        depose.connect("enter", self._sur_entree_glisser)
        depose.connect("leave", self._sur_sortie_glisser)
        self.vue.add_controller(depose)
        self.fenetre.set_child(CadreArrondi(self.vue))
        self.fenetre.set_default_size(*TAILLE_ACCUEIL)
        css = Gtk.CssProvider()
        css.load_from_data(
            b"window.axon-window, window.axon-window.background"
            b" { background: transparent; border-radius: 32px; backdrop-filter: blur(20px);"
            b" box-shadow: none; border: none; }"
        )
        # Au-dessus de ~/.config/gtk-4.0/gtk.css (priorité USER) : les thèmes
        # GTK peignent un fond opaque sur `.background`, qui masquerait le flou.
        # backdrop-filter : GTK ≥ 4.22 demande le flou au compositeur
        # (ext-background-effect-v1) sur la forme arrondie de la fenêtre. Les
        # règles de couche Hyprland (`blur = true`) n’agissent pas sur les
        # surfaces layer-shell en 0.56, c’est donc le client qui doit le demander.
        Gtk.StyleContext.add_provider_for_display(Gdk.Display.get_default(), css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 1)
        self.pont = PontSocket(SOCKET, self.depuis_axon)
        self.pont.demarrer()
        self.controle = CanalControle(SOCKET_CONTROLE, self.depuis_axon)
        self.controle.demarrer()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGUSR1, self.basculer)
        self.pid_file = SOCKET.parent / "overlay.pid"
        self.pid_file.write_text(str(os.getpid()))
        os.chmod(self.pid_file, 0o600)
        # Une seule navigation WebKit pendant toute la vie du processus.
        # Le front envoie « pret » après montage Svelte et décodage des images.
        self.vue.load_uri((ICI / "ui/index.html").as_uri())

    def _sur_depot(self, _cible, valeur, _x, _y):
        # Glisser-déposer GTK natif, pas un événement JS : pas de passage par
        # `depuis_page`, on alimente directement la même file que les pushes
        # CLI→île (`self.pont.envoyer`) — c'est l'île qui ENVOIE "joindre" ici,
        # symétrique à ce qu'elle ferait en cliquant le trombone dans le front.
        for fichier in valeur.get_files():
            chemin = fichier.get_path()
            if chemin:
                self.pont.envoyer({"type": "joindre", "chemin": chemin})
        return True

    def _sur_entree_glisser(self, _cible, _x, _y):
        self.depuis_axon({"type": "glisser", "actif": True})
        return Gdk.DragAction.COPY

    def _sur_sortie_glisser(self, _cible):
        self.depuis_axon({"type": "glisser", "actif": False})

    def basculer(self, *_args):
        self.ouvert = not self.ouvert
        self.generation += 1
        if not self.ouvert:
            self.fenetre.set_visible(False)
        self.planifier_sync()
        return True

    def ceder_au_selecteur(self, ouvert: bool):
        # La couche TOP passe au-dessus de toute fenêtre ordinaire, dont le
        # sélecteur de fichier natif (zenity/kdialog) ouvert par le CLI. On
        # descend sous les fenêtres le temps du choix plutôt que de masquer
        # l'île : pas de nouvelle présentation, la vue et le brouillon restent.
        couche = LayerShell.Layer.BOTTOM if ouvert else LayerShell.Layer.TOP
        LayerShell.set_layer(self.fenetre, couche)

    def definir_mode(self, mode, hauteur=None):
        mode = mode if mode in TAILLES else "detail"
        if mode in HAUTEUR_VARIABLE and isinstance(hauteur, (int, float)):
            bas, haut = HAUTEUR_NOTIF
            self.hauteur_notif = int(min(max(hauteur, bas), haut))
        taille = (TAILLES[mode][0], self.hauteur_notif) if mode in HAUTEUR_VARIABLE else TAILLES[mode]
        if mode == self.mode and taille == self.taille:
            return
        if (mode == "pastille") != (self.mode == "pastille"):
            LayerShell.set_margin(self.fenetre, LayerShell.Edge.TOP,
                                  MARGE_HAUT_PASTILLE if mode == "pastille" else MARGE_HAUT)
        if (mode in SANS_CLAVIER) != (self.mode in SANS_CLAVIER):
            LayerShell.set_keyboard_mode(self.fenetre, LayerShell.KeyboardMode.NONE if mode in SANS_CLAVIER
                                         else LayerShell.KeyboardMode.ON_DEMAND)
        self.mode = mode
        self.taille = taille
        self.vue.set_size_request(*taille)
        self.fenetre.set_default_size(*taille)

    def planifier_sync(self):
        if self.page_prete and not self.synchronisation:
            self.synchronisation = True
            GLib.idle_add(self.synchroniser)

    def synchroniser(self):
        self.synchronisation = False
        if not self.page_prete:
            return False
        messages, self.attente = self.attente, []
        generation = self.generation
        script = (
            "(() => { if (!window.axon) return false; "
            + json.dumps(messages, ensure_ascii=False)
            + ".forEach(m => window.axon.recevoir(m)); window.axon.ouvrir("
            + json.dumps(self.ouvert) + "); return true; })()"
        )
        self.vue.evaluate_javascript(script, -1, None, None, None, self.page_synchronisee, generation)
        return False

    def page_synchronisee(self, vue, resultat, generation):
        try:
            valeur = vue.evaluate_javascript_finish(resultat)
            if not valeur or not valeur.to_boolean():
                return
        except GLib.Error as erreur:
            print(f"Synchronisation de l’overlay impossible : {erreur}", flush=True)
            return
        if self.ouvert and self.page_prete and generation == self.generation:
            if not self.fenetre.get_visible():
                self.fenetre.present()
                self.fenetre.add_tick_callback(self.demarrer_entree, generation)

    def demarrer_entree(self, widget, clock, generation):
        # Start the prepared first pose only once the native window is mapped.
        if self.ouvert and self.page_prete and generation == self.generation:
            self.vue.evaluate_javascript("window.axon?.entree()", -1, None, None, None, None, None)
        return False

    def depuis_axon(self, message):
        if not isinstance(message, dict):
            return False
        genre = message.get("type")
        if genre == "basculer":
            self.basculer()
            return False
        if genre == "selecteur_fichier":
            self.ceder_au_selecteur(message.get("ouvert") is True)
            return False
        if genre == "connexion" and message.get("connecte") is False:
            # Le CLI peut mourir avec le sélecteur ouvert : sans ça, l'île
            # resterait sous toutes les fenêtres jusqu'au prochain lancement.
            self.ceder_au_selecteur(False)
        self.attente.append(message)
        if message.get("type") in ("demande", "confirmation", "rappel") and not self.ouvert:
            # Île fermée : un rappel s'ouvre en bulle — Axon vient le dire ;
            # une demande, en pastille que le survol déplie. Ouverte, c'est la
            # page qui choisit.
            self.ouvert = True
            self.generation += 1
            self.definir_mode("bulle" if message.get("type") == "rappel" else "pastille")
        self.planifier_sync()
        return False

    def depuis_page(self, _contenu, valeur):
        try:
            message = json.loads(valeur.to_json(0))
        except (ValueError, TypeError):
            return
        if not isinstance(message, dict):
            return
        genre = message.get("type")
        if genre == "pret":
            self.page_prete = True
            self.planifier_sync()
        elif genre == "ouvrir":
            if bool(message.get("ouvert")) != self.ouvert:
                self.basculer()
        elif genre == "mode":
            self.definir_mode(message.get("mode", "accueil"), message.get("hauteur"))
        elif genre in ("commande", "reponse_demande", "decision", "demander_commandes", "raccourci",
                       "joindre", "detacher", "demander_picker", "creer_suivi",
                       "creer_echeance", "maj_echeance", "archiver_suivi", "lier_ressource", "supprimer_suivi",
                       "demander_flux", "planifier_rappels"):
            if not self.pont.envoyer(message):
                self.depuis_axon({"type": "connexion", "connecte": False})
                self.depuis_axon({"type": "etat", "etat": "erreur", "texte": "Axon n’est pas connecté"})

    def processus_termine(self, _vue, raison):
        # Pas de boucle de reload qui ferait flasher tout l’îlot.
        self.page_prete = False
        self.fenetre.set_visible(False)
        print(f"Le processus WebKit s’est arrêté ({raison}). Relance lancer.sh.", flush=True)
        self.quit()

    def do_shutdown(self):
        if hasattr(self, "pid_file") and self.pid_file.exists():
            if self.pid_file.read_text().strip() == str(os.getpid()):
                self.pid_file.unlink(missing_ok=True)
                SOCKET.unlink(missing_ok=True)
                SOCKET_CONTROLE.unlink(missing_ok=True)
        Gtk.Application.do_shutdown(self)

    def chargement_echoue(self, _vue, _evenement, uri, erreur):
        print(f"Chargement impossible : {uri} : {erreur}", flush=True)
        return False


if __name__ == "__main__":
    Overlay().run(None)
