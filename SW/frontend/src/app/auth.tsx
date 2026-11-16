
import React from 'react';
import { useLocalSearchParams, useRouter } from 'expo-router';

import { AuthScreen } from '../screens/AuthScreen';

export default function AuthRoute() {
  const router = useRouter();

  const { mode } = useLocalSearchParams<{
    mode?: 'login' | 'register';
  }>();

  return (
    <AuthScreen
      initialMode={mode === 'register' ? 'register' : 'login'}
      onBackPress={() => router.back()}
      onLoginSuccess={(email) => {
        console.log('Login successful:', email);
        router.replace('/dashboard');
      }}
      onRegisterSuccess={(name, email) => {
        console.log('Registration successful:', name, email);
        router.replace('/dashboard');
      }}
    />
  );
}
