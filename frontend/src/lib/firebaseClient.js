'use client';

import { initializeApp, getApps } from 'firebase/app';
import { getAuth, signInWithCustomToken } from 'firebase/auth';
import { getFirestore } from 'firebase/firestore';
import { authAPI } from './api';

const firebaseConfig = {
  apiKey: process.env.NEXT_PUBLIC_FIREBASE_API_KEY,
  authDomain: process.env.NEXT_PUBLIC_FIREBASE_AUTH_DOMAIN,
  projectId: process.env.NEXT_PUBLIC_FIREBASE_PROJECT_ID,
  appId: process.env.NEXT_PUBLIC_FIREBASE_APP_ID,
};

function getFirebaseApp() {
  return getApps()[0] || initializeApp(firebaseConfig);
}

export const db = getFirestore(getFirebaseApp());

let authPromise = null;

// Signs the Firebase client into the same identity as the JWT-authenticated
// user, using a custom token minted by the backend. Firestore security rules
// key off this auth state, so it must resolve before any listener is opened.
export function ensureFirebaseAuth() {
  if (!authPromise) {
    authPromise = (async () => {
      const auth = getAuth(getFirebaseApp());
      if (auth.currentUser) return auth.currentUser;
      const { firebase_token } = await authAPI.firebaseToken();
      const cred = await signInWithCustomToken(auth, firebase_token);
      return cred.user;
    })().catch((err) => {
      authPromise = null;
      throw err;
    });
  }
  return authPromise;
}
