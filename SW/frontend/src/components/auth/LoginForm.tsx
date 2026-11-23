import React, { useState } from 'react';
import {
  Alert,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';


interface LoginFormProps {
  onLoginSuccess: (email: string) => void;
}

export function LoginForm({
  onLoginSuccess,
}: LoginFormProps) {
  const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
  
    const [showPassword, setShowPassword] = useState(false);
  
    const handleLogin = () => {
  
      if (!email.trim() || !password) {
        Alert.alert(
          'Missing information',
          'Please enter your email address and password.'
        );
        return;
      }
  
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
        Alert.alert(
          'Invalid email',
          'Please enter a valid email address.'
        );
        return;
      }
  
      // Temporary callback.
      // Real authentication will be implemented with the backend.
      onLoginSuccess(email.trim());
  
    };



  return (
          <View className="bg-white rounded-2xl p-4 border border-[#E5EAF3] shadow-sm">

            {/* EMAIL */}

            <FormLabel
              label="Email Address"
              hint="Registered email"
            />

            <FormInput
              icon="mail-outline"
              placeholder="name@example.com"
              value={email}
              onChangeText={setEmail}
              keyboardType="email-address"
              autoCapitalize="none"
            />

            {/* PASSWORD */}

            <FormLabel
              label="Password"
              hint="Your account password"
            />

            <View className="flex-row items-center bg-[#F7F9FE] border border-[#E2E8F0] rounded-xl px-3">

              <Ionicons
                name="lock-closed-outline"
                size={19}
                color="#64748B"
              />

              <TextInput
                className="flex-1 px-3 py-3 text-[#173B82] text-sm"
                placeholder="Enter your password"
                placeholderTextColor="#94A3B8"
                value={password}
                onChangeText={setPassword}
                secureTextEntry={!showPassword}
                autoCapitalize="none"
                autoCorrect={false}
              />

              <Pressable
                onPress={() => setShowPassword(!showPassword)}
                hitSlop={10}
              >

                <Ionicons
                  name={
                    showPassword
                      ? 'eye-off-outline'
                      : 'eye-outline'
                  }
                  size={20}
                  color="#64748B"
                />

              </Pressable>

            </View>

            {/* FORGOT PASSWORD */}

            <Pressable
              onPress={() =>
                Alert.alert(
                  'Password Recovery',
                  'Password recovery will be available soon.'
                )
              }
              className="self-end mt-3 mb-6"
            >

              <Text className="text-[#1764D8] text-xs font-semibold">
                Forgot password?
              </Text>

            </Pressable>

            {/* SIGN IN */}

            <Pressable
              onPress={handleLogin}
              className="bg-[#23458F] rounded-xl py-3.5 flex-row items-center justify-center active:opacity-80"
            >

              <Ionicons
                name="lock-closed"
                size={16}
                color="#FFFFFF"
              />

              <Text className="text-white font-bold text-sm ml-2">
                Sign In Securely
              </Text>

            </Pressable>

          </View>
  );
}


function FormLabel({
  label,
  hint,
}: {
  label: string;
  hint: string;
}) {
  return (
    <View className="flex-row justify-between items-center mb-1.5 mt-2">

      <Text className="text-[#173B82] text-[11px] font-medium">
        {label}
      </Text>

      <Text className="text-[#64748B] text-[9px]">
        {hint}
      </Text>

    </View>
  );
}

function FormInput({
  icon,
  ...props
}: {
  icon: keyof typeof Ionicons.glyphMap;
  placeholder: string;
  value: string;
  onChangeText: (value: string) => void;
  keyboardType?: 'default' | 'email-address';
  autoCapitalize?: 'none' | 'words';
}) {
  return (
    <View className="flex-row items-center bg-[#F7F9FE] border border-[#E2E8F0] rounded-xl px-3">

      <Ionicons
        name={icon}
        size={18}
        color="#64748B"
      />

      <TextInput
        className="flex-1 px-3 py-3 text-[#173B82] text-sm"
        placeholder={props.placeholder}
        placeholderTextColor="#94A3B8"
        value={props.value}
        onChangeText={props.onChangeText}
        keyboardType={props.keyboardType ?? 'default'}
        autoCapitalize={props.autoCapitalize ?? 'none'}
      />

    </View>
  );
}
