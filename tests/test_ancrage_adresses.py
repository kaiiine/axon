"""Une adresse de destinataire doit venir de la conversation, jamais du modèle."""
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage

from src.orchestrator.noeuds.ancrage_adresses import (
    adresses_connues, destinataires, refus_adresses_inventees)


def _appel(to, nom="gmail_send_email", **args):
    return [{"name": nom, "id": "c1", "args": {"to": to, "subject": "s", "body": "b", **args}}]


def test_une_adresse_donnee_par_l_utilisateur_est_acceptee():
    msgs = [HumanMessage(content="écris à Quentin.Dupont@Exemple.fr pour les congés")]
    assert refus_adresses_inventees(_appel("quentin.dupont@exemple.fr"), msgs) == []


def test_une_adresse_devinee_est_refusee_avec_la_marche_a_suivre():
    refus = refus_adresses_inventees(_appel("manager@entreprise.com"), [HumanMessage(content="mail au manager")])
    assert len(refus) == 1 and refus[0].status == "error" and refus[0].tool_call_id == "c1"
    assert "manager@entreprise.com" in refus[0].content and "ask_clarification" in refus[0].content


def test_une_adresse_trouvee_par_un_outil_est_acceptee():
    msgs = [HumanMessage(content="mail à Quentin"),
            ToolMessage(content="De : Quentin <quentin@acme.io>", tool_call_id="x", name="gmail_search")]
    assert refus_adresses_inventees(_appel("quentin@acme.io"), msgs) == []


def test_une_reponse_a_une_clarification_est_acceptee():
    msgs = [ToolMessage(content='{"answers": {"adresse": "q@acme.io"}}', tool_call_id="x",
                        name="ask_clarification")]
    assert refus_adresses_inventees(_appel("q@acme.io"), msgs) == []


def test_l_adresse_ecrite_par_le_modele_ne_s_ancre_pas_elle_meme():
    msgs = [HumanMessage(content="mail au manager"),
            AIMessage(content="", tool_calls=_appel("manager@entreprise.com"))]
    assert refus_adresses_inventees(_appel("manager@entreprise.com"), msgs)


def test_cc_et_bcc_sont_verifies_aussi():
    msgs = [HumanMessage(content="écris à a@b.fr")]
    assert refus_adresses_inventees(_appel("a@b.fr", cc="rh@boite.fr"), msgs)


def test_plusieurs_destinataires_dont_un_seul_invente():
    msgs = [HumanMessage(content="à a@b.fr")]
    refus = refus_adresses_inventees(_appel("a@b.fr, z@z.fr"), msgs)
    assert "z@z.fr" in refus[0].content and "a@b.fr," not in refus[0].content


def test_les_autres_outils_ne_sont_pas_concernes():
    assert refus_adresses_inventees(_appel("x@y.fr", nom="gmail_reply"), []) == []


def test_extraction_des_adresses():
    assert destinataires({"to": "Jean <j@x.fr>, k@y.org"}) == ["j@x.fr", "k@y.org"]
    assert adresses_connues([HumanMessage(content="A@B.fr.")]) == {"a@b.fr"}
