// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
import {
  createContext,
  //   MutableRefObject,
  //   PropsWithChildren,
  useCallback,
  useContext,
  useRef,
  useState,
  type MutableRefObject,
  type PropsWithChildren,
} from "react";

import type { AppLayoutProps } from "@cloudscape-design/components/app-layout";
import type { FlashbarProps } from "@cloudscape-design/components/flashbar";

// import { Tutorial, useAvailableTutorials } from './tutorial-data';

interface StoreContextType {
  state: {
    // tutorials: any[];
    toolsOpen: boolean;
    toolsTab: string;
    helpPanelData: any;
    helpPanelTopic: string;
    moduleSelected: string;
    notifications: FlashbarProps.MessageDefinition[];
  };
  actions: {
    makeHelpPanelHandler(topic: string): () => void;
    setHelpPanelTopic(helpPanelTopic: string): void;
    setHelpPanelData(helpPanelData: any): void;
    setToolsTab(toolsTab: string): void;
    setToolsOpen(toolsOpen: boolean): void;
    setModuleSelected(moduleName: string): void;
    showNotification: (notification: FlashbarProps.MessageDefinition) => void;
    removeNotification: (id: string) => void;
    clearNotifications: () => void;
    // setTutorialCompleted(tutorial: any, completed: boolean): void;
  };
  appLayoutRef: MutableRefObject<AppLayoutProps.Ref | null>;
}

const StoreContext = createContext<StoreContextType | undefined>(undefined);

export function useStore() {
  const context = useContext(StoreContext);
  if (!context) {
    throw new Error("Context is not initialized");
  }
  return context;
}

export function StoreProvider({ children }: PropsWithChildren) {
  const [toolsOpen, setToolsOpen] = useState(false);
  const [toolsTab, setToolsTab] = useState("no-help");
  const [helpPanelData, setHelpPanelData] = useState({});
  const [helpPanelTopic, setHelpPanelTopic] = useState("");
  const appLayoutRef = useRef<AppLayoutProps.Ref>(null);
  const [moduleSelected, setModuleSelected] = useState(
    "competitive-intelligence"
  );
  const [notifications, setNotifications] = useState<
    FlashbarProps.MessageDefinition[]
  >([]);

  const showNotification = useCallback(
    (notification: FlashbarProps.MessageDefinition) => {
      const id = notification.id || Math.random().toString(36).substring(2);
      setNotifications((prev) => [
        ...prev,
        {
          ...notification,
          id,
          dismissible: true,
          onDismiss: () => removeNotification(id),
        },
      ]);
    },
    []
  );

  const removeNotification = useCallback((id: string) => {
    setNotifications((prev) => prev.filter((n) => n.id !== id));
  }, []);

  const clearNotifications = useCallback(() => {
    setNotifications([]);
  }, []);

  const makeHelpPanelHandler = useCallback(
    (topic: string) => () => {
      // console.log('in call back')
      setHelpPanelTopic(topic);
      setToolsTab("no-help");
      setToolsOpen(true);
      appLayoutRef.current?.focusToolsClose();
    },
    []
  );

  //   const makeHelpPanelHandler = () => {
  //         // console.log('in call back')
  //       setHelpPanelTopic('topic');
  //       setToolsTab('help-panel');
  //       setToolsOpen(true);
  //       appLayoutRef.current?.focusToolsClose();
  //     }

  //   const [tutorials, setTutorialCompleted] = useAvailableTutorials(makeHelpPanelHandler);

  return (
    <StoreContext.Provider
      value={{
        state: {
          //   tutorials,
          toolsOpen,
          toolsTab,
          helpPanelData,
          helpPanelTopic,
          moduleSelected,
          notifications,
        },
        actions: {
          makeHelpPanelHandler,
          setHelpPanelTopic,
          setHelpPanelData,
          setToolsTab,
          setToolsOpen,
          setModuleSelected,
          showNotification,
          removeNotification,
          clearNotifications,
        },
        appLayoutRef,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
}
