import { useState, useEffect } from 'preact/hooks';
import { Modal, Input, Space, Spin } from 'antd';
// import { CKEditor } from '@ckeditor/ckeditor5-react';
// import {
//   ClassicEditor,
//   Essentials,
//   Bold,
//   Italic,
//   Underline,
//   Strikethrough,
//   Heading,
//   Paragraph,
//   Link,
//   List,
//   BlockQuote,
//   Undo,
// } from 'ckeditor5';
// import 'ckeditor5/ckeditor5.css';

type ModalInputBaseKnowledgeProps = {
  isModalOpen: boolean;
  isSaving: boolean;
  handleOk: (filename: string, productId: string, productName: string, content: string) => void;
  handleCancel: () => void;
};

const ModalInputBaseKnowledge = ({
  isModalOpen,
  isSaving,
  handleOk,
  handleCancel,
}: ModalInputBaseKnowledgeProps) => {
  //   const [editorData, setEditorData] = useState('');
  const [filename, setFilename] = useState('');
  const [productId, setProductId] = useState('');
  const [productName, setProductName] = useState('');
  const [textArea, setTextArea] = useState('');

  useEffect(() => {
    if (isModalOpen) {
      //   setEditorData('');
      setFilename('');
      setProductId('');
      setProductName('');
      setTextArea('');
    }
  }, [isModalOpen]);

  return (
    <>
      {isSaving && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 9999,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            backgroundColor: 'rgba(0, 0, 0, 0.55)',
            backdropFilter: 'blur(4px)',
            gap: '16px',
          }}
        >
          <Spin size="large" />
          <span
            style={{ color: '#fff', fontSize: '15px', fontWeight: 500, letterSpacing: '0.01em' }}
          >
            Menyimpan & mengindeks knowledge base…
          </span>
        </div>
      )}
      <Modal
        title="Input Base Knowledge"
        closable={{ 'aria-label': 'Custom Close Button' }}
        open={isModalOpen}
        onOk={() =>
          handleOk(
            filename,
            productId,
            productName,
            //  editorData,
            textArea,
          )
        }
        onCancel={handleCancel}
        okText="Save"
        confirmLoading={isSaving}
        width={800}
        destroyOnHidden
      >
        <Space orientation="vertical" style={{ width: '100%', minHeight: 300 }}>
          <div>
            <p className="font-medium mb-2">Filename</p>
            <Input
              placeholder="Judul / Nama File (misal: fitur-login)"
              value={filename}
              onChange={(e) => {
                const target = e.target as HTMLInputElement | null;
                setFilename(target?.value ?? '');
              }}
            />
          </div>
          <Space style={{ width: '100%' }}>
            <div>
              <p className="font-medium mb-2">Product ID</p>
              <Input
                placeholder="Product ID (misal: acelents)"
                value={productId}
                style={{ width: '380px' }}
                onChange={(e) => {
                  const target = e.target as HTMLInputElement | null;
                  setProductId(target?.value ?? '');
                }}
              />
            </div>
            <div>
              <p className="font-medium mb-2">Product Name</p>
              <Input
                placeholder="Product Name (misal: Acelents Website)"
                value={productName}
                style={{ width: '380px' }}
                onChange={(e) => {
                  const target = e.target as HTMLInputElement | null;
                  setProductName(target?.value ?? '');
                }}
              />
            </div>
          </Space>
          {/* <CKEditor
          editor={ClassicEditor}
          data={editorData}
          config={{
            licenseKey: 'GPL',
            plugins: [
              Essentials,
              Bold,
              Italic,
              Underline,
              Strikethrough,
              Heading,
              Paragraph,
              Link,
              List,
              BlockQuote,
              Undo,
            ],
            toolbar: [
              'heading',
              '|',
              'bold',
              'italic',
              'underline',
              'strikethrough',
              '|',
              'link',
              'bulletedList',
              'numberedList',
              'blockQuote',
              '|',
              'undo',
              'redo',
            ],
            placeholder: 'Tulis knowledge base di sini…',
          }}
          onChange={(_event: any, editor: any) => {
            setEditorData(editor.getData());
          }}
        /> */}
          <div>
            <p className="font-medium mb-2">Knowledge Base Content</p>
            <textarea
              id="knowledgeBaseContent"
              placeholder="Tulis knowledge base di sini…"
              value={textArea}
              onChange={(e) => {
                const target = e.target as HTMLInputElement | null;
                setTextArea(target?.value ?? '');
              }}
              style={{
                width: '100%',
                height: '200px',
                border: '1px solid #d9d9d9',
                borderRadius: '4px',
                padding: '8px',
              }}
            />
          </div>
        </Space>
      </Modal>
    </>
  );
};

export default ModalInputBaseKnowledge;
