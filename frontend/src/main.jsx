import React from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import ChatApp from './components/ChatApp.jsx';

createRoot(document.getElementById('root')).render(<ChatApp />);
