import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import tkinter.font as tkfont
import os
import json
from collections import defaultdict
import re


class KindleClippingsManager:
    def __init__(self, root):
        self.root = root
        self.root.title("Kindle Clippings Manager")
        self.root.geometry("900x600")
        self.root.minsize(600, 400)

        self.clippings_file = None
        self.books_data = {}

        # Largeur de base pour la colonne Titre.
        # Elle est ensuite ajustée selon le contenu.
        self._title_content_width = 600

        # Permet d'éviter de recalculer trop souvent la largeur des colonnes.
        self._adjust_columns_job = None

        # Fichier de configuration JSON dans le dossier utilisateur.
        self.config_file = os.path.join(
            os.path.expanduser("~"),
            "kindle_manager_config.json"
        )

        # Permet de différer légèrement la sauvegarde de la géométrie.
        self._save_job = None

        self.load_window_config()
        self.setup_ui()

        # Sauvegarde la géométrie quand la fenêtre est redimensionnée/déplacée.
        self.root.bind("<Configure>", self.schedule_save_window_config)

        # Sauvegarde aussi à la fermeture.
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    def setup_ui(self):
        # Frame principal
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky="nsew")

        # Bouton pour charger le fichier
        ttk.Button(
            main_frame,
            text="Charger My Clippings.txt",
            command=self.load_file
        ).grid(row=0, column=0, pady=10)

        self.file_label = ttk.Label(main_frame, text="Aucun fichier chargé")
        self.file_label.grid(row=0, column=1, padx=10, sticky=tk.W)

        # Liste des livres
        ttk.Label(
            main_frame,
            text="Livres disponibles :"
        ).grid(row=1, column=0, columnspan=2, sticky=tk.W)

        # Frame contenant le tableau et les scrollbars
        list_frame = ttk.Frame(main_frame)
        list_frame.grid(row=2, column=0, columnspan=2, sticky="nsew")

        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        y_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL)
        x_scrollbar = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL)

        # Vrai tableau avec colonnes
        self.books_tree = ttk.Treeview(
            list_frame,
            columns=("notes", "title"),
            show="headings",
            selectmode="browse",
            yscrollcommand=y_scrollbar.set,
            xscrollcommand=x_scrollbar.set
        )

        y_scrollbar.configure(command=self.books_tree.yview)
        x_scrollbar.configure(command=self.books_tree.xview)

        # En-têtes
        self.books_tree.heading("notes", text="Notes", anchor=tk.CENTER)
        self.books_tree.heading("title", text="Titre", anchor=tk.W)

        # Colonnes
        self.books_tree.column(
            "notes",
            width=80,
            minwidth=60,
            anchor=tk.CENTER,
            stretch=False
        )

        self.books_tree.column(
            "title",
            width=600,
            minwidth=200,
            anchor=tk.W,
            stretch=False
        )

        # Positionnement du tableau et des scrollbars
        self.books_tree.grid(row=0, column=0, sticky="nsew")
        y_scrollbar.grid(row=0, column=1, sticky="ns")
        x_scrollbar.grid(row=1, column=0, sticky="ew")

        # Adaptation de la largeur de la colonne Titre lors des redimensionnements
        self.books_tree.bind("<Configure>", self.adjust_tree_columns)

        # Frame pour les boutons d'action
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=3, column=0, columnspan=2, pady=10)

        ttk.Button(
            button_frame,
            text="Exporter les notes",
            command=self.export_notes
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            button_frame,
            text="Exporter ET supprimer du fichier",
            command=self.export_and_delete
        ).pack(side=tk.LEFT, padx=5)

        # Configurer le redimensionnement de la fenêtre principale
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)

        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(2, weight=1)

    def adjust_tree_columns(self, event=None):
        """
        Demande un ajustement différé de la largeur de la colonne Titre.
        """
        if self._adjust_columns_job is not None:
            self.root.after_cancel(self._adjust_columns_job)
            self._adjust_columns_job = None

        self._adjust_columns_job = self.root.after(
            50,
            self.do_adjust_tree_columns
        )

    def do_adjust_tree_columns(self):
        """
        Ajuste la largeur de la colonne Titre :
        - si le texte est court, la colonne remplit l'espace disponible ;
        - si le texte est long, la colonne devient plus large et la
          scrollbar horizontale permet d'aller voir à droite.
        """
        self._adjust_columns_job = None

        try:
            tree_width = self.books_tree.winfo_width()

            if tree_width <= 1:
                # Le widget n'est pas encore réellement affiché.
                self.adjust_tree_columns()
                return

            try:
                notes_width = int(self.books_tree.column("notes", "width"))
            except Exception:
                notes_width = 80

            # Un peu de marge pour éviter une scrollbar inutile.
            available_width = tree_width - notes_width - 35

            title_width = max(
                self._title_content_width,
                available_width
            )

            try:
                current_title_width = int(
                    self.books_tree.column("title", "width")
                )
            except Exception:
                current_title_width = 0

            if current_title_width != title_width:
                self.books_tree.column("title", width=title_width)

        except Exception:
            pass

    def load_window_config(self):
        """
        Charge la géométrie et l'état de la fenêtre depuis le fichier JSON.
        """
        try:
            if not os.path.exists(self.config_file):
                return

            with open(self.config_file, "r", encoding="utf-8") as f:
                config = json.load(f)

            geometry = config.get("geometry", "")

            # Exemples acceptés :
            # 900x600
            # 900x600+100+50
            # 900x600-20+30
            if re.match(r"^\d+x\d+([+-]\d+[+-]\d+)?$", geometry):
                self.root.geometry(geometry)

            state = config.get("state", "")

            if state in ("normal", "zoomed"):
                self.root.state(state)

        except Exception:
            pass

    def save_window_config(self):
        """
        Sauvegarde la géométrie et l'état de la fenêtre dans le fichier JSON.
        """
        self._save_job = None

        try:
            if self.root.state() == "iconic":
                return

            config = {
                "geometry": self.root.geometry(),
                "state": self.root.state(),
            }

            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(config, f, ensure_ascii=False, indent=2)

        except Exception:
            pass

    def schedule_save_window_config(self, event=None):
        """
        Attend un court instant avant de sauvegarder la géométrie,
        afin d'éviter beaucoup d'écritures pendant un redimensionnement.
        """
        if self.root.state() == "iconic":
            return

        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
            self._save_job = None

        self._save_job = self.root.after(500, self.save_window_config)

    def on_close(self):
        """
        Action effectuée à la fermeture de la fenêtre.
        """
        if self._save_job is not None:
            self.root.after_cancel(self._save_job)
            self._save_job = None

        if self._adjust_columns_job is not None:
            self.root.after_cancel(self._adjust_columns_job)
            self._adjust_columns_job = None

        self.save_window_config()
        self.root.destroy()

    def parse_clippings(self, content):
        """
        Parse le fichier My Clippings.txt
        """
        books = defaultdict(list)

        entries = content.split('==========\n')

        for entry in entries:
            entry = entry.strip()

            if not entry:
                continue

            lines = entry.split('\n')

            if len(lines) < 3:
                continue

            # Première ligne : titre et auteur
            title_line = lines[0].strip()

            # Extraire le titre (tout sauf la partie entre parenthèses à la fin)
            match = re.match(r'^(.+?)\s*\(([^)]+)\)\s*$', title_line)

            if match:
                title = match.group(1).strip()
                author = match.group(2).strip()
                book_key = f"{title} ({author})"
            else:
                book_key = title_line

            # La note commence à partir de la 3ème ligne
            note = '\n'.join(lines[2:]).strip()

            if note:
                books[book_key].append({
                    'original_entry': entry,
                    'note': note
                })

        return books

    def load_file(self):
        """
        Charge le fichier My Clippings.txt
        """
        filepath = filedialog.askopenfilename(
            title="Sélectionner My Clippings.txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not filepath:
            return

        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            self.clippings_file = filepath
            self.books_data = self.parse_clippings(content)

            # Mettre à jour l'interface
            self.file_label.config(
                text=f"Fichier chargé : {os.path.basename(filepath)}"
            )

            # Remplir le tableau
            self.refresh_books_list()

            messagebox.showinfo(
                "Succès",
                f"{len(self.books_data)} livres chargés avec succès !"
            )

        except Exception as e:
            messagebox.showerror(
                "Erreur",
                f"Erreur lors du chargement : {str(e)}"
            )

    def refresh_books_list(self):
        """
        Met à jour le tableau des livres.
        Colonne 1 : nombre de notes.
        Colonne 2 : titre du livre.
        """
        self.books_tree.delete(*self.books_tree.get_children())

        try:
            font = tkfont.Font(font=self.books_tree["font"])
        except Exception:
            font = tkfont.Font()

        max_title_width = font.measure("Titre")

        for index, book_title in enumerate(sorted(self.books_data.keys())):
            num_notes = len(self.books_data[book_title])

            self.books_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(num_notes, book_title)
            )

            title_width = font.measure(str(book_title))
            max_title_width = max(max_title_width, title_width)

        # Marge pour ne pas coller le texte au bord droit.
        self._title_content_width = max(250, max_title_width + 50)

        self.adjust_tree_columns()

    def get_selected_book(self):
        """
        Retourne le titre du livre sélectionné.
        """
        selection = self.books_tree.selection()

        if not selection:
            messagebox.showwarning(
                "Attention",
                "Veuillez sélectionner un livre"
            )
            return None

        values = self.books_tree.item(selection[0], "values")

        if not values or len(values) < 2:
            messagebox.showwarning(
                "Attention",
                "Impossible de retrouver le livre sélectionné"
            )
            return None

        return str(values[1]).strip()

    def sanitize_filename(self, filename):
        """
        Nettoie le nom de fichier pour le rendre valide.
        """
        invalid_chars = '<>:"/\\|?*'

        for char in invalid_chars:
            filename = filename.replace(char, '_')

        return filename

    def export_notes(self):
        """
        Exporte les notes du livre sélectionné.
        """
        book_title = self.get_selected_book()

        if not book_title:
            return

        notes = self.books_data.get(book_title, [])

        if not notes:
            messagebox.showwarning(
                "Attention",
                "Aucune note trouvée pour ce livre"
            )
            return

        # Créer le nom de fichier
        filename = self.sanitize_filename(book_title) + ".txt"

        # Demander où sauvegarder
        filepath = filedialog.asksaveasfilename(
            title="Sauvegarder les notes",
            initialfile=filename,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not filepath:
            return

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                for i, note_data in enumerate(notes):
                    f.write(note_data['note'])

                    # Ajouter 2 retours à la ligne entre les notes
                    # (sauf pour la dernière)
                    if i < len(notes) - 1:
                        f.write('\n\n')

            messagebox.showinfo(
                "Succès",
                f"{len(notes)} notes exportées vers :\n{filepath}"
            )

        except Exception as e:
            messagebox.showerror(
                "Erreur",
                f"Erreur lors de l'export : {str(e)}"
            )

    def export_and_delete(self):
        """
        Exporte les notes et les supprime du fichier My Clippings.txt.
        """
        book_title = self.get_selected_book()

        if not book_title:
            return

        # Confirmer l'action
        response = messagebox.askyesno(
            "Confirmation",
            f"Êtes-vous sûr de vouloir exporter les notes de '{book_title}' "
            f"et les supprimer du fichier My Clippings.txt ?\n\n"
            f"Une sauvegarde sera créée automatiquement."
        )

        if not response:
            return

        notes = self.books_data.get(book_title, [])

        if not notes:
            messagebox.showwarning(
                "Attention",
                "Aucune note trouvée pour ce livre"
            )
            return

        # Créer le nom de fichier
        filename = self.sanitize_filename(book_title) + ".txt"

        # Demander où sauvegarder
        filepath = filedialog.asksaveasfilename(
            title="Sauvegarder les notes",
            initialfile=filename,
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )

        if not filepath:
            return

        try:
            # Exporter les notes
            with open(filepath, 'w', encoding='utf-8') as f:
                for i, note_data in enumerate(notes):
                    f.write(note_data['note'])

                    if i < len(notes) - 1:
                        f.write('\n\n')

            # Créer une sauvegarde du fichier original
            backup_file = self.clippings_file + '.backup'

            with open(self.clippings_file, 'r', encoding='utf-8') as f:
                original_content = f.read()

            with open(backup_file, 'w', encoding='utf-8') as f:
                f.write(original_content)

            # Supprimer les notes du fichier My Clippings.txt
            entries_to_remove = [
                note_data['original_entry']
                for note_data in notes
            ]

            new_content = original_content

            for entry in entries_to_remove:
                # Supprimer l'entrée complète avec son séparateur
                pattern = re.escape(entry) + r'\n==========\n'
                new_content = re.sub(pattern, '', new_content)

            # Sauvegarder le nouveau contenu
            with open(self.clippings_file, 'w', encoding='utf-8') as f:
                f.write(new_content)

            # Recharger le fichier
            self.books_data = self.parse_clippings(new_content)

            # Mettre à jour le tableau
            self.refresh_books_list()

            messagebox.showinfo(
                "Succès",
                f"{len(notes)} notes exportées vers :\n{filepath}\n\n"
                f"Les notes ont été supprimées de My Clippings.txt\n"
                f"Une sauvegarde a été créée : {backup_file}"
            )

        except Exception as e:
            messagebox.showerror(
                "Erreur",
                f"Erreur lors de l'opération : {str(e)}"
            )


def main():
    root = tk.Tk()
    app = KindleClippingsManager(root)
    root.mainloop()


if __name__ == "__main__":
    main()