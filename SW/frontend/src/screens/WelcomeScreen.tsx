import React from 'react';
import { Pressable, ScrollView, Text, View } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { Ionicons } from '@expo/vector-icons';

interface WelcomeScreenProps {
  onLoginPress: () => void;
  onRegisterPress: () => void;
}

const features = [
  {
    icon: 'bluetooth' as const,
    title: '50 Hz Bluetooth Sync',
    detail: 'Real time posture tracking with low power BLE.',
    badge: '50 Hz',
  },
  {
    icon: 'pulse' as const,
    title: 'Posture monitoring',
    detail: 'Understand your posture and build better habits.',
    badge: 'Live',
  },
  {
    icon: 'notifications-outline' as const,
    title: 'Gentle reminders',
    detail: 'Get a discreet nudge when your posture shifts.',
    badge: 'Smart',
  },
];

export function WelcomeScreen({ onLoginPress, onRegisterPress }: WelcomeScreenProps) {
  return (
    <SafeAreaView className="flex-1 bg-[#F7F8FC]">
      <ScrollView
        contentContainerClassName="flex-grow px-5 pt-3 pb-5"
        showsVerticalScrollIndicator={false}
      >
        <View className="flex-row items-center gap-2.5">
          <View className="h-9 w-9 items-center justify-center rounded-xl bg-[#EAF0FF]">
            <Ionicons name="body" size={21} color="#1554C0" />
          </View>
          <Text className="text-lg font-extrabold text-[#102B61]">CorPost</Text>
        </View>

        <View className="mt-7 mb-5 items-center">
          <Text className="text-center text-[25px] font-extrabold leading-[31px] text-[#102B61]">
            Better posture, every day
          </Text>
          <Text className="mt-2 max-w-[330px] text-center text-[13px] leading-5 text-[#52627D]">
            Your wearable companion for real time posture insights and healthier habits.
          </Text>
        </View>

        <View className="gap-2.5">
          {features.map((feature) => (
            <FeatureCard key={feature.title} {...feature} />
          ))}
        </View>

        <View className="mt-5 gap-2.5">
          <Pressable
            accessibilityRole="button"
            onPress={onRegisterPress}
            className="h-12 flex-row items-center justify-center rounded-xl bg-[#0754D8] active:opacity-80"
          >
            <Text className="text-sm font-bold text-white">Create account</Text>
            <Ionicons name="arrow-forward" size={17} color="#FFFFFF" style={{ marginLeft: 8 }} />
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={onLoginPress}
            className="h-12 items-center justify-center rounded-xl border border-[#D9DFEB] bg-white active:bg-[#F0F4FC]"
          >
            <Text className="text-sm font-bold text-[#173B82]">Log in</Text>
          </Pressable>
        </View>

        <View className="mt-auto pt-5">
          <Text className="text-center text-[10px] text-[#77849B]">
            CorPost · Your posture, your health
          </Text>
        </View>
      </ScrollView>
    </SafeAreaView>
  );
}

interface FeatureCardProps {
  icon: keyof typeof Ionicons.glyphMap;
  title: string;
  detail: string;
  badge: string;
}

function FeatureCard({ icon, title, detail, badge }: FeatureCardProps) {
  return (
    <View className="rounded-2xl border border-[#E1E5EF] bg-white p-3 shadow-sm">
      <View className="mb-1.5 flex-row items-center">
        <View className="mr-2.5 h-8 w-8 items-center justify-center rounded-lg bg-[#EEF3FF]">
          <Ionicons name={icon} size={17} color="#1554C0" />
        </View>
        <Text className="flex-1 text-xs font-bold text-[#152D5B]">{title}</Text>
        <View className="rounded-full bg-[#EEF3FF] px-2 py-1">
          <Text className="text-[9px] font-semibold text-[#23458F]">{badge}</Text>
        </View>
      </View>
      <Text className="text-[11px] leading-4 text-[#52627D]">{detail}</Text>
    </View>
  );
}
