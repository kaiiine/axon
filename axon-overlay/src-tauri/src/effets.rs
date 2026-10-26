//! Le verre derrière l'île, avec l'effet natif de chaque système.
//!
//! - macOS 26 et plus : Liquid Glass ; avant : le flou de la barre des menus.
//! - Windows 11 : Mica ; Windows 10 : Acrylic.
//! - Linux : rien ici — le compositeur floute (règles Hyprland de l'île GTK).
//!
//! Doit être appelé sur le fil principal (exigé par AppKit).

use tauri::WebviewWindow;

/// Le rayon des coins de `.island` dans la page.
#[cfg_attr(not(target_os = "macos"), allow(dead_code))]
const RAYON: f64 = 32.0;

#[cfg(target_os = "macos")]
pub fn appliquer(fenetre: &WebviewWindow) {
    use window_vibrancy::{
        apply_liquid_glass, apply_vibrancy, LiquidGlassOptions, NSGlassEffectViewStyle,
        NSVisualEffectMaterial, NSVisualEffectState,
    };
    let verre = LiquidGlassOptions::new(NSGlassEffectViewStyle::Regular).radius(RAYON);
    if apply_liquid_glass(fenetre, verre).is_err() {
        let _ = apply_vibrancy(
            fenetre,
            NSVisualEffectMaterial::HudWindow,
            Some(NSVisualEffectState::Active),
            Some(RAYON),
        );
    }
}

#[cfg(target_os = "windows")]
pub fn appliquer(fenetre: &WebviewWindow) {
    use window_vibrancy::{apply_acrylic, apply_mica};
    if apply_mica(fenetre, Some(true)).is_err() {
        let _ = apply_acrylic(fenetre, Some((18, 18, 24, 125)));
    }
}

#[cfg(not(any(target_os = "macos", target_os = "windows")))]
pub fn appliquer(_fenetre: &WebviewWindow) {}
