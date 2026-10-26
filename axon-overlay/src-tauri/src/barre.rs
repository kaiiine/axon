//! L'île dans la barre du système : l'icône (barre des menus macOS, zone de
//! notification Windows) et le raccourci global, qui tous deux la basculent.

use tauri::image::Image;
use tauri::menu::{Menu, MenuItem};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::App;
use tauri_plugin_global_shortcut::{Code, Modifiers, Shortcut, ShortcutState};

use crate::ile;

/// ⌘⇧Espace sous macOS, Ctrl+Maj+Espace ailleurs.
pub fn raccourci() -> Shortcut {
    let principal = if cfg!(target_os = "macos") {
        Modifiers::SUPER
    } else {
        Modifiers::CONTROL
    };
    Shortcut::new(Some(principal | Modifiers::SHIFT), Code::Space)
}

pub fn gerer_raccourci(app: &tauri::AppHandle, etat: ShortcutState) {
    if etat == ShortcutState::Pressed {
        ile::basculer(app);
    }
}

pub fn installer(app: &App) -> tauri::Result<()> {
    let basculer = MenuItem::with_id(
        app,
        "basculer",
        "Ouvrir ou masquer Axon",
        true,
        None::<&str>,
    )?;
    let quitter = MenuItem::with_id(app, "quitter", "Quitter", true, None::<&str>)?;
    let menu = Menu::with_items(app, &[&basculer, &quitter])?;

    // macOS : une silhouette « modèle », que le système teinte selon la barre.
    let icone = if cfg!(target_os = "macos") {
        Image::from_bytes(include_bytes!("../icons/barre-modele.png"))?
    } else {
        Image::from_bytes(include_bytes!("../icons/barre.png"))?
    };

    TrayIconBuilder::with_id("axon")
        .icon(icone)
        .icon_as_template(cfg!(target_os = "macos"))
        .tooltip("Axon")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(|app, evenement| match evenement.id().as_ref() {
            "basculer" => ile::basculer(app),
            "quitter" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|icone, evenement| {
            if let TrayIconEvent::Click {
                button: MouseButton::Left,
                button_state: MouseButtonState::Up,
                ..
            } = evenement
            {
                ile::basculer(icone.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}
