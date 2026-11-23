import React, { useState } from 'react';
import {
  Alert,
  Pressable,
  Text,
  TextInput,
  View,
} from 'react-native';
import { Ionicons } from '@expo/vector-icons';

interface RegisterFormProps {
  onRegisterSuccess: (name: string, email: string) => void;
}

export function RegisterForm({
    onRegisterSuccess,
  }: RegisterFormProps) {
  
    const [fullName, setFullName] = useState('');
    const [email, setEmail] = useState('');
    const [password, setPassword] = useState('');
  
    const [showPassword, setShowPassword] = useState(false);
    const [acceptedPrivacy, setAcceptedPrivacy] = useState(false);
  
    const passwordStrength = getPasswordStrength(password);
  
    const handleRegister = () => {
  
      if (!fullName.trim() || !email.trim() || !password) {
        Alert.alert(
          'Missing information',
          'Please complete all required fields.'
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
  
      if (passwordStrength.score < 2) {
        Alert.alert(
          'Weak password',
          'Your password must contain at least 8 characters and one number.'
        );
        return;
      }
  
      if (!acceptedPrivacy) {
        Alert.alert(
          'Consent required',
          'Please accept the data processing terms to continue.'
        );
        return;
      }
  
      // Temporary callback.
      // Real account creation will be connected to the backend later.
      onRegisterSuccess(fullName.trim(), email.trim());
  
    };

  return (
          <View className="bg-white rounded-2xl p-4 border border-[#E5EAF3] shadow-sm">

            {/* FULL NAME */}

            <FormLabel
              label="Full Name"
              hint="Required"
            />

            <FormInput
              icon="person-outline"
              placeholder="Enter your full name"
              value={fullName}
              onChangeText={setFullName}
              autoCapitalize="words"
            />

            {/* EMAIL */}

            <FormLabel
              label="Email Address"
              hint="Institutional / Clinical"
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
              hint="Strong password"
            />

            <View className="flex-row items-center bg-[#F7F9FE] border border-[#E2E8F0] rounded-xl px-3">

              <Ionicons
                name="lock-closed-outline"
                size={19}
                color="#64748B"
              />

              <TextInput
                className="flex-1 px-3 py-3 text-[#173B82] text-sm"
                placeholder="Create a password"
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
                  name={showPassword ? 'eye-off-outline' : 'eye-outline'}
                  size={20}
                  color="#64748B"
                />
              </Pressable>

            </View>

            {/* PASSWORD STRENGTH */}

            <View className="flex-row gap-1.5 mt-2">

              {[0, 1, 2, 3].map((index) => (
                <View
                  key={index}
                  className={`flex-1 h-1.5 rounded-full ${
                    index < passwordStrength.score
                      ? passwordStrength.color
                      : 'bg-[#E5EAF3]'
                  }`}
                />
              ))}

            </View>

            <View className="flex-row items-center mt-2 mb-4">
              <Ionicons
                name="checkmark-circle-outline"
                size={13}
                color="#2563EB"
              />

              <Text className="text-[#64748B] text-[10px] ml-1">
                Minimum 8 characters, 1 number and 1 letter
              </Text>
            </View>

            {/* PRIVACY CONSENT */}

            <Pressable
              onPress={() => setAcceptedPrivacy(!acceptedPrivacy)}
              className="flex-row items-start mb-5"
            >

              <View
                className={`w-5 h-5 rounded-md items-center justify-center mr-3 ${
                  acceptedPrivacy
                    ? 'bg-[#1764D8]'
                    : 'border border-[#94A3B8] bg-white'
                }`}
              >
                {acceptedPrivacy && (
                  <Ionicons
                    name="checkmark"
                    size={15}
                    color="#FFFFFF"
                  />
                )}
              </View>

              <Text className="text-[#475569] text-[10px] flex-1 leading-4">
                I agree to the processing of my posture-related
                biometric data for health purposes and accept
                the Privacy Policy.
              </Text>

            </Pressable>

            {/* CREATE ACCOUNT */}

            <Pressable
              onPress={handleRegister}
              className="bg-[#23458F] rounded-xl py-3.5 flex-row items-center justify-center active:opacity-80"
            >

              <Ionicons
                name="lock-closed"
                size={16}
                color="#FFFFFF"
              />

              <Text className="text-white font-bold text-sm ml-2">
                Create Secure Account
              </Text>

            </Pressable>

          </View>
  );
}


// Reusable label component

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

// Reusable input component

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

function getPasswordStrength(password: string) {

  let score = 0;

  if (password.length >= 8) score++;
  if (/[A-Z]/.test(password)) score++;
  if (/[a-z]/.test(password)) score++;
  if (/[0-9]/.test(password)) score++;

  let color = 'bg-[#EF4444]';

  if (score >= 2) color = 'bg-[#F59E0B]';
  if (score >= 3) color = 'bg-[#2563EB]';
  if (score === 4) color = 'bg-[#16A34A]';

  return { score, color };
}
