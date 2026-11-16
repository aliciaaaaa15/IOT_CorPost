
import React from 'react';
import { SafeAreaView } from 'react-native-safe-area-context';
import {
  Text,
  View,
  Pressable,
} from 'react-native';

import { useRouter } from 'expo-router';

export default function DashboardRoute() {
  const router = useRouter();

  return (
    <SafeAreaView className="flex-1 bg-[#F4F7FD]">
      <View className="flex-1 px-6 py-8">

        <Text className="text-2xl font-extrabold text-[#173B82]">
          Welcome to CorPost!
        </Text>

        <Text className="text-[#64748B] mt-2">
          Your posture monitoring journey starts here.
        </Text>

        <View className="bg-white rounded-2xl p-5 mt-8 border border-[#E2E8F0]">

          <Text className="text-[#173B82] font-bold text-lg">
            Device Connection
          </Text>

          <Text className="text-[#64748B] text-sm mt-2">
            Your CorPost device is not connected.
            Connect your device to start monitoring your posture.
          </Text>

          <Pressable
            className="bg-[#23458F] rounded-xl py-3 mt-5 items-center"
          >
            <Text className="text-white font-bold">
              Connect Device
            </Text>
          </Pressable>

        </View>

      </View>
    </SafeAreaView>
  );
}
