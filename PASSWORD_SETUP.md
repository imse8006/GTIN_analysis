# 🔒 Configuration du Mot de Passe

## Protection par Mot de Passe Activée

Le dashboard est maintenant protégé par un mot de passe. Voici comment le configurer :

## 🔧 Configuration Locale (Développement)

1. **Créer le fichier de secrets** :
   - Créez un dossier `.streamlit` dans votre projet (s'il n'existe pas)
   - Créez un fichier `secrets.toml` dans `.streamlit/`
   - Copiez le contenu de `.streamlit/secrets.toml.example`

2. **Définir votre mot de passe** :
   ```toml
   PASSWORD = "votre_mot_de_passe_ici"
   ```
## ☁️ Configuration Streamlit Cloud

### Méthode 1 : Via l'Interface Web

1. Allez sur https://share.streamlit.io
2. Sélectionnez votre app
3. Cliquez sur **"Settings"** (⚙️) en haut à droite
4. Allez dans l'onglet **"Secrets"**
5. Ajoutez :
   ```toml
   PASSWORD = "votre_mot_de_passe_secu"
   ```
6. Cliquez sur **"Save"**
7. L'app redéploiera automatiquement

### Méthode 2 : Via le Fichier secrets.toml

1. Créez un fichier `.streamlit/secrets.toml` dans votre repo
2. Ajoutez :
   ```toml
   PASSWORD = "votre_mot_de_passe_secu"
   ```
3. ⚠️ **ATTENTION** : Ne commitez JAMAIS ce fichier sur GitHub !
4. Pour Streamlit Cloud, ajoutez-le via l'interface (Méthode 1)

## 🔐 Bonnes Pratiques

- ✅ Utilisez un mot de passe fort (min 12 caractères, majuscules, minuscules, chiffres, symboles)
- ✅ Ne partagez le mot de passe que via un canal sécurisé
- ✅ Changez le mot de passe régulièrement
- ❌ Ne commitez JAMAIS le fichier `secrets.toml` sur GitHub
- ❌ N'utilisez pas le mot de passe par défaut en production

## 📝 Exemple de Mot de Passe Fort

```
Gt1n@2024!D4shb0ard
```

## 🔄 Changer le Mot de Passe

1. **Streamlit Cloud** : Modifiez dans Settings > Secrets
2. **Local** : Modifiez `.streamlit/secrets.toml`
3. Redémarrez l'application

## 🆘 Si vous oubliez le Mot de Passe

1. **Streamlit Cloud** : Accédez à Settings > Secrets pour le voir/modifier
2. **Local** : Vérifiez `.streamlit/secrets.toml` ou réinitialisez-le
