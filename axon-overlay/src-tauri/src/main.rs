//! L'île Axon hors Linux/Wayland : la page de `../ui` dans une fenêtre sans
//! bordure, transparente, toujours au premier plan, pilotée depuis la barre
//! du système. L'île GTK (`overlay.py`) reste l'hôte de Linux/Wayland.

#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

mod barre;
mod canal;
mod effets;
mod ile;

use serde_json::{json, Value};
use tauri::{DragDropEvent, Manager, WindowEvent};
use tauri_plugin_global_shortcut::GlobalShortcutExt;

#[tauri::command]
fn depuis_page(app: tauri::AppHandle, message: Value) {
    ile::depuis_page(&app, message);
}

fn main() {
    tauri::Builder::default()
        // Un second lancement (clic sur l'app, raccourci du système) bascule
        // l'île déjà ouverte au lieu d'en créer une autre.
        .plugin(tauri_plugin_single_instance::init(|app, _args, _cwd| {
            ile::basculer(app)
        }))
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_handler(|app, _raccourci, evenement| {
                    barre::gerer_raccourci(app, evenement.state)
                })
                .build(),
        )
        .manage(ile::Ile::default())
        .manage(canal::ClientOverlay::default())
        .invoke_handler(tauri::generate_handler![depuis_page])
        .setup(|app| {
            #[cfg(target_os = "macos")]
            app.set_activation_policy(tauri::ActivationPolicy::Accessory);

            if let Some(fenetre) = app.get_webview_window(ile::FENETRE) {
                effets::appliquer(&fenetre);
            }
            barre::installer(app)?;
            canal::demarrer(app.handle())?;
            if let Err(erreur) = app.global_shortcut().register(barre::raccourci()) {
                eprintln!("axon-ile : raccourci global indisponible ({erreur})");
            }
            Ok(())
        })
        .on_window_event(|fenetre, evenement| match evenement {
            // Fermer l'île la masque : elle reste joignable par Axon.
            WindowEvent::CloseRequested { api, .. } => {
                api.prevent_close();
                ile::depuis_page(
                    fenetre.app_handle(),
                    json!({ "type": "ouvrir", "ouvert": false }),
                );
            }
            WindowEvent::DragDrop(depot) => glisser_deposer(fenetre.app_handle(), depot),
            _ => {}
        })
        .run(tauri::generate_context!())
        .expect("axon-ile : démarrage impossible");
}

/// Un fichier déposé sur l'île est joint au prochain message, comme le
/// trombone de la page.
fn glisser_deposer(app: &tauri::AppHandle, depot: &DragDropEvent) {
    match depot {
        DragDropEvent::Enter { .. } => {
            ile::depuis_axon(app, json!({ "type": "glisser", "actif": true }))
        }
        DragDropEvent::Leave => ile::depuis_axon(app, json!({ "type": "glisser", "actif": false })),
        DragDropEvent::Drop { paths, .. } => {
            ile::depuis_axon(app, json!({ "type": "glisser", "actif": false }));
            for chemin in paths {
                ile::depuis_page(app, json!({ "type": "joindre", "chemin": chemin }));
            }
        }
        _ => {}
    }
}
