
import React from 'react';
import { useRouter } from 'expo-router';

import { WelcomeScreen } from '../screens/WelcomeScreen';

export default function WelcomeRoute() {
  const router = useRouter();

  return (
    <WelcomeScreen
      onLoginPress={() =>
        router.push('/auth?mode=login')
      }
      onRegisterPress={() =>
        router.push('/auth?mode=register')
      }
    />
  );
}
