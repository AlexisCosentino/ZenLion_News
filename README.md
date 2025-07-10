# 📈 ZenLion News Trading Bot

ZenLion est un robot de trading automatique développé en Python avec la librairie MetaTrader5. Il exécute des stratégies de trading autour des **news économiques majeures**, avec détection automatique du symbole le plus pertinent selon la devise concernée.

## ⚙️ Fonctionnalités principales

- Connexion automatique à MT5 (Admiral Markets)
- Détection et parsing des news (API externe)
- Sélection du symbole optimal avec spread minimal
- Implémentation de la stratégie **Breakout Sandwich** & **Trend post-news**
- Ordres automatiques de type `Buy Stop` / `Sell Stop` avec expiration

---

## 📊 Stratégie 1 : Breakout Sandwich (inspirée de l’approche de Joe Trader)

### 📌 Principe
La stratégie Breakout Sandwich consiste à détecter la volatilité potentielle autour d'une news, **sans chercher de tendance**, mais en capturant un breakout brutal juste après la publication.

### 🧠 Logique de fonctionnement

1. **5 minutes avant la news** :
   - Récupération des 5 dernières bougies en M1.
   - Détection du **plus haut** et du **plus bas** sur ces 5 bougies.
   - Ajout d’un buffer de 3 pips au-dessus et en dessous.

2. **Juste avant la news** :
   - Placement de deux ordres en attente :
     - `Buy Stop` au-dessus du plus haut (avec +3 pips).
     - `Sell Stop` en dessous du plus bas (avec -3 pips).
   - Les deux ordres ont une **expiration courte** (1 à 2 minutes max).

3. **Après la news** :
   - L’un des deux ordres est déclenché si un breakout a lieu.
   - L’autre est automatiquement expiré ou supprimé.
   - Un stop-loss et un take-profit peuvent être automatiquement placés.

### 🧮 Paramètres techniques

| Élément         | Valeur par défaut |
|----------------|-------------------|
| Lookback       | 5 bougies M1      |
| Buffer pips    | 3 pips            |
| Expiration     | 1 à 2 minutes     |
| Type d’ordre   | Buy Stop / Sell Stop |
| SL/TP          | À définir selon ton risk management |

---

## 📊 2. Stratégie "Trend Post-News"

### 💡 Objectif
Entrer dans la tendance déjà amorcée **quelques minutes après la news**, quand le marché a commencé à digérer l’information.

### ⚙️ Méthodologie

1. **5 minutes après la news :**
   - Récupération des **3 dernières bougies M1**.

2. **Détection de tendance courte :**
   - Si 2 bougies ou plus sont haussières (`close > open`) **et** la dernière clôture est au-dessus de la moyenne des plus hauts précédents ⇒ `buy`.
   - Si 2 bougies ou plus sont baissières (`close < open`) **et** la dernière clôture est en dessous de la moyenne des plus bas ⇒ `sell`.

3. **Exécution d'un trade directionnel unique :**
   - Achat ou vente au marché selon la direction détectée.
