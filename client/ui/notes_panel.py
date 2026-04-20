"""
Notes Panel — свободные заметки к дню.

Текстовое поле внизу каждого DayPanel для быстрых пометок:
"Звонил поставщику, сказал перезвонить в четверг"
"Цены обновятся после 15-го"

Сворачивается в одну строку "📝 Заметки..." если пусто,
или показывает превью первой строки если есть текст.
"""


class NotesPanel:
    """
    Текстовые заметки привязанные к конкретному дню.

    Хранение: одна строка в модели DayPlan.notes (plain text).
    """

    def __init__(self, parent_frame, day_date):
        self.parent = parent_frame
        self.day_date = day_date
        self.expanded = False
        self.text = ""

    def toggle(self):
        """Показать/скрыть текстовое поле."""
        self.expanded = not self.expanded
        self._refresh()

    def save(self):
        """Сохранить текст заметки."""
        # TODO: прочитать из CTkTextbox, сохранить в модель
        pass

    def _refresh(self):
        """Перерисовать."""
        # TODO: Реализовать
        pass
