# UX principles

The first version showed everything to everyone. This version answers one question per
screen, for one role.

| Pattern | Where | Why |
|---|---|---|
| **Role-based navigation** | Home « Qui êtes-vous ? », header | Each person sees 1 or 2 screens instead of 5 |
| **Next best action** | « Traiter le dossier suivant » | A handler never has to choose what to open: the most urgent free case comes first |
| **One primary button per screen** | Every page | The eye goes to the next step. Everything else is secondary. |
| **Purpose line** | Under every title | One sentence saying what the screen is for |
| **Progressive disclosure** | « Détails techniques » closed by default; « + Ajouter un champ » | Tokens, cost and the masked prompt are there for those who need them, hidden for the others |
| **Defaults are the AI's answer** | Case form | Nothing to click when the AI is right; a change is automatically "corrigé" |
| **Evidence next to the claim** | Highlighted quotes, coloured swatch next to each field | The handler checks a value in one glance instead of rereading the e-mail |
| **Words, not percentages** | « Confiance élevée / moyenne / faible » | A handler needs a judgement, not 0.73 |
| **Status in words + colour** | Badges | Readable by colour-blind users and screen readers |
| **Measured vs assumed** | Pilotage: green « mesuré », orange « hypothèses » | Nobody mistakes a projection for a result |
| **Safe by default** | Reject needs a reason; lease lock; read-only notices | Errors are prevented, not just reported |
| **Keyboard first** | Ctrl + Entrée, focusable rows, Enter opens | A handler processes dozens of cases in a row |
| **Feedback** | Toasts after each action; skeletons while loading | The user always knows the action worked |
| **Errors you can act on** | RFC 9457 `detail` in French and a request reference | « Dossier pris en charge par Sophie » instead of « 409 » |

## Screen by role

| Role | Lands on | Primary action |
|---|---|---|
| Gestionnaire | Corbeille | Traiter le dossier suivant → Valider le dossier |
| Responsable | Pilotage | (read) · edit assumptions |
| Auditeur | Journal d'audit | Vérifier l'intégrité |
| Équipe IA | Modèle IA | Lancer une évaluation · Appliquer une configuration |
