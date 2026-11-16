
import React, { useEffect, useRef, useState } from 'react';

import {
  Animated,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from 'react-native';

import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

import { LoginForm } from '../components/auth/LoginForm';
import { RegisterForm } from '../components/auth/RegisterForm';

type AuthMode = 'login' | 'register';

interface AuthScreenProps {
  initialMode?: AuthMode;
  onBackPress: () => void;
  onLoginSuccess: (email: string) => void;
  onRegisterSuccess: (name: string, email: string) => void;
}

export function AuthScreen({
  initialMode = 'login',
  onBackPress,
  onLoginSuccess,
  onRegisterSuccess,
}: AuthScreenProps) {

  const [mode, setMode] = useState<AuthMode>(initialMode);

  const formProgress = useRef(new Animated.Value(1)).current;
  const entryDirection = useRef(1);

  const switchMode = (newMode: AuthMode) => {
    if (newMode === mode) return;

    entryDirection.current = newMode === 'register' ? 1 : -1;
    formProgress.setValue(0);
    setMode(newMode);
  };

  useEffect(() => {
    Animated.spring(formProgress, {
      toValue: 1,
      stiffness: 220,
      damping: 24,
      mass: 0.8,
      useNativeDriver: true,
    }).start();

  }, [mode, formProgress]);

  const translateX = formProgress.interpolate({
    inputRange: [0, 1],
    outputRange: [entryDirection.current * 28, 0],
  });

  return (
    <SafeAreaView className="flex-1 bg-[#F4F7FD]">

      <KeyboardAvoidingView
        className="flex-1"
        behavior={Platform.OS === 'ios' ? 'padding' : undefined}
      >

        <ScrollView
          className="flex-1"
          contentContainerClassName="px-5 pt-3 pb-6"
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >

          {/* HEADER */}

          <View className="flex-row items-center justify-between mb-5">

            <Pressable
              onPress={onBackPress}
              className="w-11 h-11 bg-white rounded-xl items-center justify-center border border-[#E2E8F0]"
            >
              <Ionicons
                name="arrow-back"
                size={21}
                color="#173B82"
              />
            </Pressable>

            <View className="flex-row items-center bg-white rounded-full px-4 py-2 border border-[#E2E8F0]">

              <View className="w-6 h-6 rounded-md bg-[#23458F] items-center justify-center mr-2">
                <Ionicons
                  name="accessibility"
                  size={17}
                  color="#FFFFFF"
                />
              </View>

              <Text className="text-[#173B82] font-extrabold">
                CorPost
              </Text>

            </View>

            <View className="w-11 h-11 bg-white rounded-xl items-center justify-center border border-[#E2E8F0]">
              <Ionicons
                name="shield-checkmark"
                size={21}
                color="#1764D8"
              />
            </View>

          </View>

          {/* INTRODUCTION */}

          <View className="mb-5">

            <View className="self-start flex-row items-center bg-[#E2ECFF] rounded-full px-3 py-1 mb-2">
              <View className="w-1.5 h-1.5 bg-[#2864D8] rounded-full mr-2" />

              <Text className="text-[#23458F] text-[9px] font-bold tracking-wider">
                SECURE MEDICAL DATA
              </Text>
            </View>

            <Text className="text-[#101D35] text-2xl font-extrabold">
              {mode === 'login'
                ? 'Welcome Back'
                : 'Secure CorPost Access'}
            </Text>

            <View className="flex-row items-start mt-2">

              <Ionicons
                name="shield-checkmark-outline"
                size={15}
                color="#1764D8"
              />

              <Text className="text-[#64748B] text-xs ml-2 flex-1 leading-5">
                {mode === 'login'
                  ? 'Sign in securely to access your personal posture monitoring dashboard.'
                  : 'Your biometric data is protected. Your privacy matters to us.'}
              </Text>

            </View>

          </View>

          {/* AUTH TABS */}

          <View className="flex-row bg-[#E4EBF8] rounded-xl p-1 mb-5">

            <AuthTab
              label="Log In"
              icon="log-in-outline"
              active={mode === 'login'}
              onPress={() => switchMode('login')}
            />

            <AuthTab
              label="Register"
              icon="person-add-outline"
              active={mode === 'register'}
              onPress={() => switchMode('register')}
            />

          </View>

          {/* ANIMATED FORM */}

          <Animated.View
            style={{
              opacity: formProgress,
              transform: [{ translateX }],
            }}
          >

            {mode === 'login' ? (
              <LoginForm
                onLoginSuccess={onLoginSuccess}
              />
            ) : (
              <RegisterForm
                onRegisterSuccess={onRegisterSuccess}
              />
            )}

          </Animated.View>

          {/* PRIVACY NOTICE */}

          <View className="flex-row items-center bg-[#EDF3FF] border border-[#E0E9FA] rounded-xl p-3 mt-3">

            <View className="w-8 h-8 bg-white rounded-full items-center justify-center mr-3">
              <Ionicons
                name="lock-closed-outline"
                size={16}
                color="#23458F"
              />
            </View>

            <Text className="text-[#64748B] text-[10px] flex-1 leading-4">
              Your angular measurements remain private
              and are only accessible through your account.
            </Text>

          </View>

          {/* FOOTER */}

          <View className="flex-row items-center justify-center mt-4">
            <View className="w-1.5 h-1.5 bg-[#2864D8] rounded-full mr-2" />

            <Text className="text-[#64748B] text-[10px]">
              BLE 5.2 · Secure Device Connection
            </Text>
          </View>

        </ScrollView>

      </KeyboardAvoidingView>

    </SafeAreaView>
  );
}

// AUTH TAB COMPONENT


function AuthTab({
  label,
  icon,
  active,
  onPress,
}: {
  label: string;
  icon: keyof typeof Ionicons.glyphMap;
  active: boolean;
  onPress: () => void;
}) {
  return (
    <Pressable
      onPress={onPress}
      style={[
        styles.authTab,
        active && styles.authTabActive,
      ]}
    >
      <Ionicons
        name={icon}
        size={15}
        color={active ? '#173B82' : '#64748B'}
      />

      <Text
        className={`text-xs ml-1 ${
          active
            ? 'text-[#173B82] font-bold'
            : 'text-[#64748B]'
        }`}
      >
        {label}
      </Text>

      {active && (
        <View className="w-1.5 h-1.5 bg-[#2864D8] rounded-full ml-2" />
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  authTab: {
    flex: 1,
    paddingVertical: 12,
    borderRadius: 8,
    alignItems: 'center',
    justifyContent: 'center',
    flexDirection: 'row',
  },
  authTabActive: {
    backgroundColor: '#FFFFFF',
    elevation: 2,
    shadowColor: '#000000',
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.08,
    shadowRadius: 2,
  },
});
