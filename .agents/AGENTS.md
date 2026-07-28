# FluentYTDL Workspace Rules

These rules are specific to the FluentYTDL project and must be followed by all AI agents working in this workspace.

## Typography and UI Consistency
- **Font Weight for Hierarchy**: Never use `BodyLabel` for prominent elements like titles, subtitles, or instruction texts. Always use `StrongBodyLabel` or `SubtitleLabel` to prevent text from rendering too thin or blurry under native Windows scaling.
- **High Contrast for Secondary Text**: Do not hardcode standard grays like `Qt.GlobalColor.darkGray` or arbitrary RGB values like `QColor(160, 160, 160)` for descriptive text (e.g., `CaptionLabel`). Instead, use `setTextColor(QColor(96, 96, 96), QColor(210, 210, 210))` to guarantee crisp contrast in both Light and Dark modes.
- **Modifying QFluentWidgets Safely**: Never monkey-patch core QFluentWidgets components (like `SettingCard`) globally. Custom subclassed components (such as `InlineComboBoxCard`) may replace expected widgets (e.g., swapping `CaptionLabel` for a standard `QLabel`), leading to `AttributeError` on missing methods like `setTextColor`. Instead, when you need to batch update UI elements, use explicit iteration (e.g., `self.findChildren(SettingCard)`) inside the page's `__init__` block and pair it with strict `hasattr` checks before invoking methods.
