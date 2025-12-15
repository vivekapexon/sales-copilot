// Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
// SPDX-License-Identifier: MIT-0
import { forwardRef, useEffect, useState } from "react";

import AppLayoutToolbar from "@cloudscape-design/components/app-layout-toolbar";
import { I18nProvider } from "@cloudscape-design/components/i18n";
import enMessages from "@cloudscape-design/components/i18n/messages/all.en.json";

import type { AppLayoutProps } from "@cloudscape-design/components/app-layout";
import {
  Box,
  BreadcrumbGroup,
  Link,
  List,
  SideNavigation,
  SpaceBetween,
  type SideNavigationProps,
} from "@cloudscape-design/components";
import { Outlet, useNavigate } from "react-router-dom";
import HeaderComponent from "../components/Header";
import { useStore } from "../store";
import { getSessions } from "../api/api-service";
import { useAuth } from "../context/AuthContext";
import { ScrollableList } from "../components/Common";

const MainLayout = forwardRef<AppLayoutProps.Ref, AppLayoutProps>(
  function CustomAppLayout(props, ref) {
    const navigate = useNavigate();
    const { state, actions, appLayoutRef } = useStore();
    const { chatHistoryList, setChatHistoryList } = useAuth();
    const [filterText] = useState("");
    const filteredChatHistory = chatHistoryList.filter((item) =>
      item.title.toLowerCase().includes(filterText.toLowerCase())
    );
    const items: SideNavigationProps.Item[] = [
      // { type: "link", text: "Home", href: "/" },
      { type: "link", text: "Pre-Call Analysis", href: "/" },
      { type: "link", text: "Post-Call Analysis", href: "/post-call" },
      // { type: "divider" },
    ];
    const [navigationOpen, setNavigationOpen] = useState<boolean>(true);
    const [selectedModule, setSelectedModule] = useState<any>(items[0]);

    const onNavChange = (link: any) => {
      console.log(link);
      setSelectedModule(link);

      navigate(link.href);
    };

    const breadcrumbs = [
      { text: "Home", href: "/" },
      // simple breadcrumb mapping; more sophisticated mapping can be added later
      location.pathname !== "/"
        ? { text: location.pathname.replace("/", ""), href: location.pathname }
        : undefined,
    ].filter(Boolean) as { text: string; href: string }[];

    useEffect(() => {
      if (state.notifications.length > 0) {
        window.scrollTo({ top: 0, behavior: "smooth" });
      }
      console.log(ref);
    }, [state.notifications]);

    useEffect(() => {
      const module = selectedModule?.text
        .split(" ")[0]
        .replace("-", "")
        .toLowerCase();
      const response = getSessions(module);
      response.then((res) => {
        console.log(res);
        setChatHistoryList(res.sessions);
      });
      console.log(selectedModule);
    }, [selectedModule]);

    return (
      <I18nProvider locale="en" messages={[enMessages]}>
        <HeaderComponent />
        <AppLayoutToolbar
          ref={appLayoutRef}
          {...props}
          navigation={
            <>
              <SideNavigation
                activeHref={location.pathname}
                header={{ text: "Menu", href: "/" }}
                items={items}
                // itemsControl
                onFollow={(event) => {
                  event.preventDefault();
                  onNavChange(event.detail);
                  // navigate(event.detail.href);
                }}
              />
              <hr
                className="awsui_divider_l0dv0_1u5ju_232 awsui_divider-header_l0dv0_1u5ju_232"
                role="presentation"
              />
              <Box padding={"s"}>
                <Box variant="h3">Chat History</Box>
                <SpaceBetween size="s">
                  {/* <TextFilter
                    filteringText={filterText}
                    filteringPlaceholder="Search chats"
                    onChange={({ detail }) =>
                      setFilterText(detail.filteringText)
                    }
                  /> */}
                  <ScrollableList>
                    <List
                      ariaLabel="List with icons and actions"
                      items={filteredChatHistory}
                      renderItem={(item) => ({
                        id: item.session_id,
                        content: (
                          <Link href={`?session=${item.session_id}`}>
                            {item.title}
                          </Link>
                          // <NavLink
                          //   to={`?session=${item.session_id}`}
                          //   replace={true}
                          // >
                          //   {item.title}
                          // </NavLink>
                        ),
                      })}
                    />
                  </ScrollableList>
                </SpaceBetween>
              </Box>
            </>
          }
          navigationOpen={navigationOpen}
          onNavigationChange={({ detail }) => setNavigationOpen(detail.open)}
          breadcrumbs={
            <BreadcrumbGroup items={breadcrumbs} ariaLabel="Breadcrumbs" />
          }
          // toolsHide={true}
          //   toolsOpen={state.toolsOpen}
          onToolsChange={(event) => {
            console.log(event);
            actions.setToolsOpen(event.detail.open);
          }}
          toolsWidth={400}
          //   notifications={<Notifications />}
          //   tools={
          //     <>
          //       <Tabs
          //         activeTabId={state.toolsTab}
          //         onChange={(event) =>
          //           actions.setToolsTab(event.detail.activeTabId)
          //         }
          //         tabs={[
          //           {
          //             id: "help-panel",
          //             label: "Information",
          //             content: helpPanelContent[state.helpPanelTopic],
          //           },
          //         ]}
          //       />
          //     </>
          //   }
          content={<Outlet />}
          //   {...props}
        />
      </I18nProvider>
    );
  }
);

export default MainLayout;
