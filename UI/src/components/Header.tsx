import TopNavigation from "@cloudscape-design/components/top-navigation";

const HeaderComponent = () => {
  return (
    <TopNavigation
      identity={{
        href: "/",
        title: "Field Intelligence Concierge – Sales Call Excellence",
        logo: {
          src: "aws-logo.svg",
          alt: "App logo",
        },
      }}
      utilities={[
        {
          type: "button",
          iconName: "notification",
          title: "Notifications",
          ariaLabel: "Notifications",
          onClick: () => alert("No new notifications"),
        },
        {
          type: "menu-dropdown",
          text: "User",
          description: "Administrator",
          iconName: "user-profile",
          items: [
            // { id: "profile", text: "Profile" },
            // { id: "settings", text: "Settings" },
            // { id: "signout", text: "Sign out" }
          ],
          onItemClick: (item) => {
            if (item.detail.id === "signout") alert("Signing out…");
          },
        },
      ]}
    />
  );
};

export default HeaderComponent;
