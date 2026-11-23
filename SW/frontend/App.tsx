
import './global.css';

import React from 'react';
import { Alert } from 'react-native';
import { SafeAreaProvider } from 'react-native-safe-area-context';

import { WelcomeScreen } from './src/screens/WelcomeScreen';

export default function App() {

  const handleLogin = () => {
    Alert.alert('Iniciar sesión', 'Próximamente');
  };

  const handleRegister = () => {
    Alert.alert('Crear cuenta', 'Próximamente');
  };

  return (
    <SafeAreaProvider>
      <WelcomeScreen
        onLoginPress={handleLogin}
        onRegisterPress={handleRegister}
      />
    </SafeAreaProvider>
  );
}
