// Import the SDKs you need from the CDN (Modular SDK)
import { initializeApp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-app.js";
import { getAnalytics } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-analytics.js";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, signInWithEmailAndPassword } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-auth.js";
import { getFirestore, doc, getDoc, setDoc, collection, query, where, limit, getDocs, onSnapshot, addDoc, updateDoc, serverTimestamp } from "https://www.gstatic.com/firebasejs/10.8.0/firebase-firestore.js";

const firebaseConfig = {
  apiKey: "AIzaSyDUsUkHSR2uz5vNglHZnKTT5VihALXEVv0",
  authDomain: "agency-caf07.firebaseapp.com",
  projectId: "agency-caf07",
  storageBucket: "agency-caf07.firebasestorage.app",
  messagingSenderId: "915699040450",
  appId: "1:915699040450:web:8d78f3612839e141957b5b",
  measurementId: "G-X9YCWY6ZTP"
};

// Initialize Firebase
const app = initializeApp(firebaseConfig);
const analytics = getAnalytics(app);
const auth = getAuth(app);
const db = getFirestore(app);
const googleProvider = new GoogleAuthProvider();

export { 
  app, analytics, auth, db, googleProvider, signInWithPopup, signOut, signInWithEmailAndPassword,
  doc, getDoc, setDoc, collection, query, where, limit, getDocs, onSnapshot, addDoc, updateDoc, serverTimestamp 
};
