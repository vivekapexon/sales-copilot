import { SpaceBetween, Button, Box } from "@cloudscape-design/components";
import Modal from "@cloudscape-design/components/modal";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface LogModalProps {
  content: any;
  setShowModal: (showModal: boolean) => void;
  showModal: boolean;
}
const LogModal = ({ content, showModal, setShowModal }: LogModalProps) => {
  return (
    <Modal
      onDismiss={() => setShowModal(false)}
      visible={showModal}
      footer={
        <Box float="right">
          <SpaceBetween direction="horizontal" size="xs">
            <Button variant="link" onClick={() => setShowModal(false)}>
              Cancel
            </Button>
            <Button variant="primary" onClick={() => setShowModal(false)}>
              Ok
            </Button>
          </SpaceBetween>
        </Box>
      }
      header="All Logs"
    >
      <Markdown remarkPlugins={[remarkGfm]}>
        {content && content.length ? content : "No Logs to Display"}
      </Markdown>
    </Modal>
  );
};

export default LogModal;
